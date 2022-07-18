import os
import logging

from odoo import models

_logger = logging.getLogger(__name__)

beneficiary_base_id_type = os.getenv("PROGRAM_ENROLLMENT_ON_IMPORT_BENEFICIARY_BASE_ID", None)
beneficiary_base_id_label = os.getenv("PROGRAM_ENROLLMENT_ON_IMPORT_BENEFICIARY_BASE_ID_LABEL", "Related Base ID")


class BeneficiaryXLSXReport(models.AbstractModel):
    _name = 'report.xlsx.beneficiary'
    _inherit = ['report.report_xlsx.abstract']
    _description = 'Beneficary xlsx report model'

    def _get_objs_for_report(self, docids, data):
        if data.get("use_active_domain", "false") == "true":
            active_domain = data.get("active_domain", [])
            return self.env[self.env.context.get('active_model')].search(active_domain)
        if docids:
            ids = docids
        elif data and 'context' in data:
            ids = data["context"].get('active_ids', [])
        else:
            ids = self.env.context.get('active_ids', [])
        return self.env[self.env.context.get('active_model')].browse(ids)

    def generate_xlsx_report(self, workbook, data, objs):
        sheet = workbook.add_worksheet('Beneficiaries Report')
        ben_fields = self.env["openg2p.beneficiary"]._fields
        sheet.write(0, 0, beneficiary_base_id_label)
        sheet.write(0, 1, ben_fields["program_ids"].string)
        for i, obj in enumerate(objs):
            ben_base_id = ""
            for iden in obj.identities:
                if iden.category_id.code == beneficiary_base_id_type:
                    ben_base_id = iden.name
                    break
            programs_str = ", ".join([prog.name for prog in obj.program_ids])
            sheet.write(i+1, 0, ben_base_id)
            sheet.write(i+1, 1, programs_str)