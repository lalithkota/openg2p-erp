import os
import logging
import itertools
import time

from odoo import api, models, fields
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

should_create_beneficiary = os.getenv("PROGRAM_ENROLLMENT_ON_IMPORT_SHOULD_CREATE_BENEFICIARY","false")
beneficiary_base_id_type = os.getenv("PROGRAM_ENROLLMENT_ON_IMPORT_BENEFICIARY_BASE_ID", None)
beneficiary_base_id_label = os.getenv("PROGRAM_ENROLLMENT_ON_IMPORT_BENEFICIARY_BASE_ID_LABEL", "Related Base ID")
create_beneficiary_default_street = os.getenv("PROGRAM_ENROLLMENT_ON_IMPORT_CREATE_BENEFICIARY_DEFAULT_STREET", "-")
create_beneficiary_default_city = os.getenv("PROGRAM_ENROLLMENT_ON_IMPORT_CREATE_BENEFICIARY_DEFAULT_CITY", "-")
create_beneficiary_default_state = os.getenv("PROGRAM_ENROLLMENT_ON_IMPORT_CREATE_BENEFICIARY_DEFAULT_STATE", "Karnataka")
create_beneficiary_default_country = os.getenv("PROGRAM_ENROLLMENT_ON_IMPORT_CREATE_BENEFICIARY_DEFAULT_COUNTRY", "India")


class ProgramEnrollmentImport(models.Model):
    _inherit = "openg2p.program.enrollment"

    program_amount = fields.Float(
        string="Amount", required=False, default=0.0
    )
    total_amount = fields.Float(
        string="Total Remuneration", required=False, default=0.0
    )
    related_ben_base_id = fields.Char(compute="_compute_related_base_id", store=False, string=beneficiary_base_id_label)
    related_ben_programs = fields.Many2many(string="Beneficiary Listed Programs", related="beneficiary_id.program_ids", store=False)

    @api.depends("beneficiary_id")
    def _compute_related_base_id(self):
        for record in self:
            for iden in record.beneficiary_id.identities:
                if iden.category_id.code == beneficiary_base_id_type:
                    # _logger.info("Identity FOUND!! "+str(iden.name))
                    record.related_ben_base_id = iden.name

    @api.multi
    def import_models(self, fields, columns, options, data_generator, dryrun=False):
        all_data = list(data_generator)
        columns = all_data[0]
        ben_base_id_cat = None
        if beneficiary_base_id_type:
            ben_base_id_cat = self.env["openg2p.beneficiary.id_category"].search([("code", "=", beneficiary_base_id_type)], limit=1)
            if not ben_base_id_cat or ben_base_id_cat.name not in columns:
                return {
                    'messages': [{
                        'type': 'error',
                        'message': 'Improperly Configured on import base Id. Or Base Id not found in Data',
                        'record': False,
                    }]
                }

        curr_company_id = self.env.user.company_id.id
        
        ben_error_count = 0
        ben_merge_count = 0
        ben_create_count = 0
        enrol_error_count = 0
        enrol_merge_count = 0
        enrol_create_count = 0
        total_count = 0
        error_messages = []
        success_ids = []
        for row in all_data[1:]:
            total_count += 1
            if total_count%100 == 0:
                _logger.info("Program Enrollment Import: Total Records Updated: %d. Enrollments Created: %d. Enrollments Merged: %d. Error Enrollments: %d. Beneficaries Created: %d. Beneficaries Merged: %d. Error Beneficaries: %d." % (total_count, enrol_create_count, enrol_merge_count, enrol_error_count, ben_create_count, ben_merge_count, ben_error_count))
            row_data = dict(zip(columns, row))

            program_id_label = self._fields["program_id"].string
            date_start_label = self._fields["date_start"].string
            date_end_label = self._fields["date_end"].string
            amount_label = self._fields["program_amount"].string
            total_amount_label = self._fields["total_amount"].string
            state_label = self._fields["state"].string

            program_name = row_data[program_id_label] if program_id_label in row_data.keys() else None
            enrol_date_start = row_data[date_start_label] if date_start_label in row_data.keys() else None
            enrol_date_end = row_data[date_end_label] if date_end_label in row_data.keys() else None
            enrol_program_amount = row_data[amount_label] if amount_label in row_data.keys() else None
            enrol_total_amount = row_data[total_amount_label] if total_amount_label in row_data.keys() else None
            enrol_state = row_data[state_label] if state_label in row_data.keys() else None

            existing_bens = None

            # checking if beneficiary exists and creating if required
            if beneficiary_base_id_type:
                ben_id_from_data = row_data[ben_base_id_cat.name]
                existing_bens = self.env["openg2p.beneficiary.id_number"].sudo().search(
                    [
                        ("name", "=", ben_id_from_data),
                        ("category_id","=", ben_base_id_cat.id),
                    ]
                )
                if len(existing_bens) == 0 and should_create_beneficiary != "true":
                    error_messages.append({
                        'type': 'error',
                        'message': 'Beneficiary not found',
                        'record': str(row_data)
                    })
                    ben_error_count += 1
                    continue
                elif len(existing_bens) == 0 and should_create_beneficiary == "true":
                    try:
                        existing_bens = self.create_ben_with_data(ben_id_from_data, ben_base_id_cat, row_data, curr_company_id)
                        ben_create_count += 1
                    except Exception as e:
                        error_messages.append({
                            'type': 'error',
                            'message': 'Error Creating Beneficiary: ' + str(e),
                            'record': str(row_data)
                        })
                        ben_error_count += 1
                elif len(existing_bens) == 1 and should_create_beneficiary == "true":
                    try:
                        self.merge_ben_belonging_company(existing_bens, curr_company_id)
                        # self.merge_ben_with_data(existing_bens, row_data, curr_company_id)
                        ben_merge_count += 1
                    except Exception as e:
                        error_messages.append({
                            'type': 'error',
                            'message': 'Error merging Beneficiary: ' + str(e),
                            'record': str(row_data)
                        })
                        ben_error_count += 1
                elif len(existing_bens) == 1:
                    pass
                # else len(existing_bens) is >1 or <0
                else:
                    raise ValidationError("Improper Beneficiary Data found in db")
            
            # checking if the current program enrollment exists and creating/merging accordingly
            if not program_name:
                continue
            
            program_id = self.env["openg2p.program"].search([("name", "=", program_name),('company_id','=', self.env.user.company_id.id),("state","=","active")], limit=1)
            if len(program_id) == 0:
                continue

            existing_enrols = self.search([("program_id", "=", program_id.id),("beneficiary_id", "=", existing_bens.beneficiary_id.id), ("state", "in", ("open", "draft"))])
            if len(existing_enrols) == 0:
                try:
                    enrol = self.import_create_program_enroll_sql({
                        "program_id": program_id.id,
                        "beneficiary_id": existing_bens.beneficiary_id.id,
                        "date_start": enrol_date_start if enrol_date_start else program_id.date_start,
                        "date_end": enrol_date_end if enrol_date_end else program_id.date_end,
                        "program_amount": enrol_program_amount if enrol_program_amount else 0.0,
                        "total_amount": enrol_total_amount if enrol_total_amount else 0.0,
                        "state": self.get_state_key_from_value(enrol_state) if enrol_state else "open"
                    })[0]
                    success_ids.append(enrol)
                    # enrol = self.create({
                    #     "program_id": program_id.id,
                    #     "beneficiary_id": existing_bens.beneficiary_id.id,
                    #     "date_start": enrol_date_start if enrol_date_start else program_id.date_start,
                    #     "date_end": enrol_date_end if enrol_date_end else program_id.date_end,
                    #     "program_amount": enrol_program_amount if enrol_program_amount else 0.0,
                    #     "total_amount": enrol_total_amount if enrol_total_amount else 0.0,
                    #     "state": self.get_state_key_from_value(enrol_state) if enrol_state else "open"
                    # })
                    # success_ids.append(enrol.id)
                    enrol_create_count += 1
                except Exception as e:
                    error_messages.append({
                        'type': 'error',
                        'message': str(e),
                        'record': str(row_data)
                    })
                    enrol_error_count += 1
            elif len(existing_enrols) == 1:
                try:
                    existing_enrols.write({
                        "program_id": program_id.id,
                        "beneficiary_id": existing_bens.beneficiary_id.id,
                        "date_start": enrol_date_start if enrol_date_start else program_id.date_start,
                        "date_end": enrol_date_end if enrol_date_end else program_id.date_end,
                        "program_amount": enrol_program_amount if enrol_program_amount else 0.0,
                        "total_amount": enrol_total_amount if enrol_total_amount else 0.0,
                        "state": self.get_state_key_from_value(enrol_state) if enrol_state else "open"
                    })
                    success_ids.append(existing_enrols.id)
                    enrol_merge_count += 1
                except Exception as e:
                    error_messages.append({
                        'type': 'error',
                        'message': str(e),
                        'record': str(row_data)
                    })
                    enrol_error_count += 1
            # else len(existing_enrols) is >1 or <0
            else:
                raise ValidationError("Improper Program Enrollments found in db")

        # return super(ProgramEnrollmentImport, self).do(fields, columns, options, dryrun)
        _logger.info("Import Complete. Total Records Updated: %d. Enrollments Created: %d. Enrollments Merged: %d. Error Enrollments: %d. Beneficaries Created: %d. Beneficaries Merged: %d. Error Beneficaries: %d." % (total_count, enrol_create_count, enrol_merge_count, enrol_error_count, ben_create_count, ben_merge_count, ben_error_count))
        return {
            'ids': success_ids if success_ids else [],
            'messages': error_messages
        }

    def create_ben_with_data(self, ben_base_id, ben_base_id_cat, row_data, curr_company_id):
        data = self.prepare_data_ben(ben_base_id, row_data)
        data["company_id"] = curr_company_id
        data["belonging_company_ids"] = "," + str(curr_company_id) + ","
        ben = self.import_create_ben_sql(data)[0]
        if beneficiary_base_id_type:
            return self.env["openg2p.beneficiary.id_number"].browse(self.import_create_record_sql(
                "openg2p.beneficiary.id_number",
                {
                    "name": ben_base_id,
                    "category_id": ben_base_id_cat.id,
                    "beneficiary_id": ben
                }
            )[0])
        # ben = self.env["openg2p.beneficiary"].create(data)
        # if beneficiary_base_id_type:
        #     return self.env["openg2p.beneficiary.id_number"].create(
        #         {
        #             "name": ben_base_id,
        #             "category_id": ben_base_id_cat.id,
        #             "beneficiary_id": ben.id
        #         }
        #     )
        return None
    
    def merge_ben_with_data(self, existing_ben_base_id, row_data, curr_company_id):
        data = self.prepare_data_ben(existing_ben_base_id.name, row_data)
        existing_ben_base_id.beneficiary_id.write(data)
        return existing_ben_base_id

    def merge_ben_belonging_company(self, existing_ben_base_id, curr_company_id):
        existing_ben_base_id.beneficiary_id.write(
            {
                "belonging_company_ids": str(curr_company_id)
            }
        )
        return existing_ben_base_id
    
    def prepare_data_ben(self, ben_base_id, row_data):
        street_label = self.env["openg2p.beneficiary"]._fields["street"].string
        state_label = self.env["openg2p.beneficiary"]._fields["state_id"].string
        country_label = self.env["openg2p.beneficiary"]._fields["country_id"].string
        city_label = self.env["openg2p.beneficiary"]._fields["city"].string
        display_name_label = self._fields["beneficiary_id"].string

        street = row_data[street_label] if street_label in row_data.keys() else create_beneficiary_default_street
        city = row_data[city_label] if city_label in row_data.keys() else create_beneficiary_default_city
        state = row_data[state_label].split(" (", 1)[0] if state_label in row_data.keys() else create_beneficiary_default_state
        country = row_data[country_label] if country_label in row_data.keys() else create_beneficiary_default_country

        country_id = self.env["res.country"].search([("name", "=", country)], limit=1).id
        state_id = self.env["res.country.state"].search([("name", "=", state), ("country_id", "=", country_id)], limit=1).id

        display_name = row_data[display_name_label] if display_name_label in row_data.keys() else (str(ben_base_id) + " _")
        first_name = display_name.split(" ", 1)[0]
        last_name = display_name.split(" ", 1)[1].split(" (", 1)[0]
        
        return {
            "firstname": first_name,
            "lastname": last_name,
            "street": street,
            "city": city,
            "state_id": state_id,
            "country_id": country_id,
        }
    
    def get_state_key_from_value(self, value):
        for k,v in self._fields["state"].selection:
            if v == value:
                return k
        return None
    
    def import_create_record_sql(self, model_name, vals, is_relation=False):
        if isinstance(vals, dict):
            vals = [vals]
        if not vals:
            return []
        
        all_keys = set()
        for each_value in vals:
            all_keys.update(each_value.keys())
        if not is_relation:
            all_keys.update(["active","create_uid","create_date","write_uid","write_date"])
        query = "INSERT INTO " + model_name.replace(".","_") + " ("
        for i, key in enumerate(all_keys):
            if i != 0:
                query += ","
            query += key
        query += ") VALUES ("
        for i, value in enumerate(vals):
            if i != 0:
                query += " ,("
            
            if not is_relation:
                value["active"] = True
                value["create_uid"] = self.env.user.id
                value["create_date"] = fields.Datetime.now()
                value["write_uid"] = self.env.user.id
                value["write_date"] = fields.Datetime.now()
            for j, key in enumerate(all_keys):
                if j != 0:
                    query += ','
                curr_val = value.get(key, None)
                if not curr_val:
                    query += "NULL"
                elif isinstance(curr_val, int):
                    query += str(curr_val)
                elif isinstance(curr_val, bool):
                    query += "TRUE" if curr_val else "NULL"
                else:
                    query += "'" + str(curr_val) + "'"
            query += ")"
        if not is_relation:
            self.env.cr.execute(query + " RETURNING id" + ";")
            return [i[0] for i in self.env.cr.fetchall()]
        else:
            self.env.cr.execute(query + ";")
            return None
    
    def import_create_ben_sql(self, vals):
        if isinstance(vals, dict):
            vals = [vals]
        for value in vals:
            value["ref"] = self.env["openg2p.beneficiary"]._generate_ref()
        return self.import_create_record_sql("openg2p.beneficiary", vals)
    
    def import_create_program_enroll_sql(self, vals):
        if isinstance(vals, dict):
            vals = [vals]
        return_id = self.import_create_record_sql("openg2p.program.enrollment", vals)
        rel_vals = [
            {
                "openg2p_beneficiary_id": value["beneficiary_id"],
                "openg2p_program_id": value["program_id"],
            }
            for value in vals
        ]
        self.import_create_record_sql("openg2p_beneficiary_openg2p_program_rel", rel_vals, is_relation=True)
        return return_id