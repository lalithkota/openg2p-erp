# -*- coding: utf-8 -*-
from odoo import fields, models, api


class ProgramEnrollmentEnrollWizard(models.TransientModel):
    _name = "program.enrollment.enroll.wizard"
    _inherit = [ "beneficiary.enroll.wizard" ]

    def get_objs_active(self):
        program_enrol_obj = self.env["openg2p.program.enrollment"]
        if self.use_active_domain:
            pre_existing_program_enrols = program_enrol_obj.search(
                self.env.context.get("active_domain")
            )
        else:
            pre_existing_program_enrols = program_enrol_obj.browse(self.env.context.get("active_ids"))

        # if len(pre_existing_program_enrols) > 1000:
        #     pre_existing_program_enrols = pre_existing_program_enrols.sudo().with_delay()

        beneficiaries = set()
        for enroll in pre_existing_program_enrols:
            beneficiaries.add(enroll.beneficiary_id)
        return list(beneficiaries)