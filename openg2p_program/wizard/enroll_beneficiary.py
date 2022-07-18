# -*- coding: utf-8 -*-
import logging

from odoo import fields, models, api

_logger = logging.getLogger(__name__)


class EnrollWizard(models.TransientModel):
    """
    A wizard to manage the creation/removal of enroll users.
    """

    _name = "beneficiary.enroll.wizard"
    _description = "Enroll Into Program"

    program_id = fields.Many2one(
        "openg2p.program",
        string="Program",
        required=True,
        domain=lambda self: [("state","=","active"),('company_id','child_of',[self.env.user.company_id.id])]
    )
    # category_id = fields.Many2one(
    #     "openg2p.program.enrollment_category",
    #     string="Classification",
    # )
    date_start = fields.Date(
        "Enrollment Date",
        required=True,
        default=fields.Date.context_today,
        help="Start date of the program enrollment.",
    )
    date_end = fields.Date(
        "Enrollment End",
        required=False,
        help="End date of the program enrollment.",
    )
    program_amount = fields.Float(
        string="Amount", required=False, default=0.0
    )
    total_amount = fields.Float(
        string="Total Remuneration", required=False, default=0.0
    )
    use_active_domain = fields.Boolean("Use active domain")
    auto_confirm = fields.Boolean("Auto Confirm Enrollments", default=True)

    def get_objs_active(self):
        beneficiary_obj = self.env["openg2p.beneficiary"]
        if self.use_active_domain:
            beneficiaries = beneficiary_obj.search(
                self.env.context.get("active_domain")
            )
        else:
            beneficiaries = beneficiary_obj.browse(self.env.context.get("active_ids"))

        # if len(beneficiaries) > 1000:
        #     beneficiaries = beneficiaries.sudo().with_delay()
        return beneficiaries

    @api.multi
    def action_apply(self):
        _logger.info("Wizard started Enrollments.")
        self.ensure_one()
        beneficiaries = self.get_objs_active()        

        total_count = 0
        enroll_create_arr = []
        for record in beneficiaries:
            if total_count % 100 == 0:
                _logger.info("Wizard Program Enrollments: Total Records Updated: %d." % total_count)
            total_count += 1
            # enroll_exists = False
            _logger.info("Point 1")
            enrol_exists = self.env["openg2p.program.enrollment"].search(
                [
                    ("beneficiary_id","=",record.id),
                    ("program_id","=",self.program_id.id),
                    ("state", "in", ("open", "draft")),
                ]
            )
            _logger.info("Point 1.25")
            if len(enrol_exists) > 0:
                _logger.info("Point 1.5")
                enrol_exists.write(
                    {
                        "date_start": self.date_start,
                        "date_end": self.date_end if self.date_end else self.program_id.date_end,
                        "program_amount": self.program_amount,
                        "total_amount": self.total_amount,
                    }
                )
            elif len(enrol_exists) == 0:
                _logger.info("Point 2")
                enroll_create_arr.append({
                    "beneficiary_id": record.id,
                    "program_id": self.program_id.id,
                    # "category_id": self.category_id.id,
                    "date_start": self.date_start,
                    "date_end": self.date_end if self.date_end else self.program_id.date_end,
                    "program_amount": self.program_amount,
                    "total_amount": self.total_amount,
                    "state": "open" if self.auto_confirm else "draft",
                })
            _logger.info("Point 3")
        _logger.info("Point 3.5")
        self.env["openg2p.program.enrollment"].create(enroll_create_arr)
        _logger.info("Point 4")
        return {"type": "ir.actions.act_window_close"}
