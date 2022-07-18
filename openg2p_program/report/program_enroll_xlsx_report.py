import logging

from odoo import models

_logger = logging.getLogger(__name__)


class ProgramEnrollXLSXReport(models.AbstractModel):
    _name = 'report.xlsx.program.enrollment'
    _inherit = ['report.report_xlsx.abstract']
    _description = 'Program Enrollment xlsx report model'

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
        prog_enroll_fields = self.env["openg2p.program.enrollment"]._fields
        state_sel_dict = dict(prog_enroll_fields["state"].selection)
        sheet.write(0,0,prog_enroll_fields["related_ben_base_id"].string)
        sheet.write(0,1,prog_enroll_fields["program_id"].string)
        sheet.write(0,2,prog_enroll_fields["date_start"].string)
        sheet.write(0,3,prog_enroll_fields["date_end"].string)
        sheet.write(0,4,prog_enroll_fields["program_amount"].string)
        sheet.write(0,5,prog_enroll_fields["total_amount"].string)
        sheet.write(0,6,prog_enroll_fields["state"].string)
        for i, obj in enumerate(objs):
            sheet.write(i+1,0,obj.related_ben_base_id)
            sheet.write(i+1,1,obj.program_id.name)
            sheet.write(i+1,2,str(obj.date_start) if obj.date_start else "")
            sheet.write(i+1,3,str(obj.date_end) if obj.date_end else "")
            sheet.write(i+1,4,str(obj.program_amount))
            sheet.write(i+1,5,str(obj.total_amount))
            sheet.write(i+1,6,state_sel_dict[obj.state])