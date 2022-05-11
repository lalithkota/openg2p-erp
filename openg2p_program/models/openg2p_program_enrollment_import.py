import os
import logging
import itertools
import time

from odoo import api, models, fields
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

should_create_beneficiary = os.getenv("PROGRAM_ENROLLMENT_ON_IMPORT_SHOULD_CREATE_BENEFICIARY","false")
beneficiary_base_id_label = os.getenv("PROGRAM_ENROLLMENT_ON_IMPORT_BENEFICIARY_BASE_ID_LABEL", "Related Base ID")
create_beneficiary_default_street = os.getenv("PROGRAM_ENROLLMENT_ON_IMPORT_CREATE_BENEFICIARY_DEFAULT_STREET", "-")
create_beneficiary_default_city = os.getenv("PROGRAM_ENROLLMENT_ON_IMPORT_CREATE_BENEFICIARY_DEFAULT_CITY", "-")
create_beneficiary_default_state = os.getenv("PROGRAM_ENROLLMENT_ON_IMPORT_CREATE_BENEFICIARY_DEFAULT_STATE", 593)
create_beneficiary_default_country = os.getenv("PROGRAM_ENROLLMENT_ON_IMPORT_CREATE_BENEFICIARY_DEFAULT_COUNTRY", 104)


class ProgramEnrollmentImport(models.Model):
    _inherit = "openg2p.program.enrollment"

    program_ammount = fields.Float(
        string="Ammount", required=False, default=0.0
    )
    total_ammount = fields.Float(
        string="Total Remuneration", required=False, default=0.0
    )
    related_ben_programs = fields.Many2many(string="Beneficiary Listed Programs", related="beneficiary_id.program_ids", store=False)
    related_ben_base_id = fields.Char(string=beneficiary_base_id_label, related="beneficiary_id.firstname", store=False)

    @api.multi
    def import_models(self, fields, columns, options, data_generator, dryrun=False):
        if beneficiary_base_id_label.lower() not in columns:
            return {
                'messages': [{
                    'type': 'error',
                    'message': beneficiary_base_id_label + ' not found in Data',
                    'record': False,
                }]
            }
        
        ben_error_count = 0
        ben_merge_count = 0
        ben_create_count = 0
        enrol_error_count = 0
        enrol_merge_count = 0
        enrol_create_count = 0
        total_count = 0
        error_messages = []
        success_ids = []
        time_initial = time.time()
        for row in itertools.islice(data_generator,1,None):
            total_count += 1
            if total_count == 1:
                _logger.info("PROGRAM_ENROL_IMPORT. No of Rows updated: %d .timestamp: %s" % (total_count, str(time.time()-time_initial)))
            elif total_count == 10:
                _logger.info("PROGRAM_ENROL_IMPORT. No of Rows updated: %d .timestamp: %s" % (total_count, str(time.time()-time_initial)))
            elif total_count == 100:
                _logger.info("PROGRAM_ENROL_IMPORT. No of Rows updated: %d .timestamp: %s" % (total_count, str(time.time()-time_initial)))
            elif total_count == 1000:
                _logger.info("PROGRAM_ENROL_IMPORT. No of Rows updated: %d .timestamp: %s" % (total_count, str(time.time()-time_initial)))
            elif total_count == 10000:
                _logger.info("PROGRAM_ENROL_IMPORT. No of Rows updated: %d .timestamp: %s" % (total_count, str(time.time()-time_initial)))
            elif total_count == 50000:
                _logger.info("PROGRAM_ENROL_IMPORT. No of Rows updated: %d .timestamp: %s" % (total_count, str(time.time()-time_initial)))
                break
            row_data = dict(zip(columns, row))

            enrol_program_name = row_data[self._fields["program_id"].string.lower()]
            enrol_date_start = row_data[self._fields["date_start"].string.lower()]
            enrol_date_end = row_data[self._fields["date_end"].string.lower()]
            enrol_program_ammount = row_data[self._fields["program_ammount"].string.lower()]
            enrol_total_ammount = row_data[self._fields["total_ammount"].string.lower()]
            enrol_state = row_data[self._fields["state"].string.lower()]

            existing_bens = None

            # checking if beneficiary exists and creating if required
            ben_id_from_data = row_data[beneficiary_base_id_label.lower()]
            existing_bens = self.env["openg2p.beneficiary"].search([("firstname", "=", ben_id_from_data)])
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
                    existing_bens = self.create_ben_with_data(ben_id_from_data, row_data)
                    ben_create_count += 1
                except Exception as e:
                    error_messages.append({
                        'type': 'error',
                        'message': 'Error Creating Beneficiary: ' + str(e),
                        'record': str(row_data)
                    })
                    ben_error_count += 1
            elif len(existing_bens) == 1 and should_create_beneficiary == "true":
                # try:
                #     self.merge_ben_with_data(existing_bens, row_data)
                #     ben_merge_count += 1
                # except Exception as e:
                #     error_messages.append({
                #         'type': 'error',
                #         'message': 'Error merging Beneficiary: ' + str(e),
                #         'record': str(row_data)
                #     })
                #     ben_error_count += 1
                pass
            elif len(existing_bens) == 1:
                pass
            # else len(existing_bens) is >1 or <0
            else:
                raise ValidationError("Improper Beneficiary Data found in db")
            
            # checking if the current program enrollment exists and creating/merging accordingly
            if not enrol_program_name or not enrol_date_start:
                continue
            program_id = self.env["openg2p.program"].search([("name", "=", enrol_program_name)], limit=1)
            existing_enrols = self.search([("program_id", "=", program_id.id),("beneficiary_id", "=", existing_bens.id)])
            if len(existing_enrols) == 0:
                try:
                    enrol_dict = {
                        "program_id": program_id.id,
                        "beneficiary_id": existing_bens.id,
                        "date_start": enrol_date_start,
                    }
                    if enrol_date_end:
                        enrol_dict["date_end"] = enrol_date_end
                    elif program_id.date_end:
                        enrol_dict["date_end"] = program_id.date_end
                    if enrol_program_ammount:
                        enrol_dict["program_ammount"] = enrol_program_ammount
                    if enrol_total_ammount:
                        enrol_dict["total_ammount"] = enrol_total_ammount
                    enrol_dict["state"] = self.get_state_key_from_value(enrol_state) if enrol_state else "open"
                    
                    enrol = self.create(enrol_dict)
                    success_ids.append(enrol.id)
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
                    enrol_dict = {
                        "program_id": program_id.id,
                        "beneficiary_id": existing_bens.id,
                        "date_start": enrol_date_start,
                    }
                    if enrol_date_end:
                        enrol_dict["date_end"] = enrol_date_end
                    elif program_id.date_end:
                        enrol_dict["date_end"] = program_id.date_end
                    if enrol_program_ammount:
                        enrol_dict["program_ammount"] = enrol_program_ammount
                    if enrol_total_ammount:
                        enrol_dict["total_ammount"] = enrol_total_ammount
                    enrol_dict["state"] = self.get_state_key_from_value(enrol_state) if enrol_state else "open"

                    existing_enrols.write(enrol_dict)
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
        response = {
            'messages': error_messages
        }
        if len(success_ids)>0:
            response['ids'] = success_ids
        return response

    def create_ben_with_data(self, ben_base_id, row_data):
        data = self.prepare_data_ben(ben_base_id, row_data)
        return self.env["openg2p.beneficiary"].create(data)
    
    def merge_ben_with_data(self, existing_ben, row_data):
        data = self.prepare_data_ben(existing_ben.firstname, row_data)
        existing_ben.write(data)
        return existing_ben
    
    def prepare_data_ben(self, ben_base_id, row_data):
        street = create_beneficiary_default_street
        city = create_beneficiary_default_city
        state_id = create_beneficiary_default_state
        country_id = create_beneficiary_default_country

        first_name = str(ben_base_id)
        last_name = "_"
        
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