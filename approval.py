from datetime import datetime
from trytond.model import Workflow, ModelSQL, ModelView, fields
from trytond.pyson import Eval, Bool
from trytond.pool import Pool
from trytond.transaction import Transaction

__all__ = ['Group', 'GroupUser', 'Request']


class Group(ModelSQL, ModelView):
    'Approval Group'
    __name__ = 'approval.group'
    name = fields.Char('Name', required=True)
    model = fields.Many2One('ir.model', 'Model', domain=[
            ('id', 'in', Eval('valid_models', [])),
            ], depends=['valid_models'])
    valid_models = fields.Function(fields.Many2Many('ir.model', None, None,
                'Valid Models'), 'get_valid_models')
    users = fields.Many2Many('approval.group-res.user', 'group', 'user',
        'Users')

    @staticmethod
    def default_valid_models():
        res = Pool().get('approval.group').get_models_from_request()
        print "XXX: ", res
        print "--" * 10
        return res

    @classmethod
    def get_valid_models(cls, groups, name):
        models = cls.get_models_from_request()
        res = {}
        for group in groups:
            res[group.id] = models
        return res

    @staticmethod
    def get_models_from_request():
        pool = Pool()
        Request = pool.get('approval.request')
        Model = pool.get('ir.model')
        return [x.id for x in Model.search([
                    ('model', 'in', Request._get_document()),
                    ])]


class GroupUser(ModelSQL):
    'Approval Group - Users'
    __name__ = 'approval.group-res.user'
    group = fields.Many2One('approval.group', 'Group', required=True)
    user = fields.Many2One('res.user', 'User', required=True)


class Request(Workflow, ModelSQL, ModelView):
    'Approval Request'
    __name__ = 'approval.request'
    document = fields.Reference('Document', selection='get_document',
        required=True)
    version = fields.Integer('Version', readonly=True, states={
            'invisible': ~Bool(Eval('version')),
            })
    group = fields.Many2One('approval.group', 'Group', required=True,
        domain=[
            ['OR',
                [('model', '=', None)],
                [('model', '=', Eval('model'))],
                ]], depends=['model'])
    model = fields.Function(fields.Many2One('ir.model', 'Model'),
        'on_change_with_model')
    request_date = fields.DateTime('Request Date', required=True)
    description = fields.Text('Description')
    # Cancelled state will be used when the document is moved back to draft,
    # for example.
    state = fields.Selection([
            ('pending', 'Pending'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
            ('cancelled', 'Cancelled'),
            ], 'State', required=True)
    user = fields.Many2One('res.user', 'User', states={
            'required': Eval('state').in_(['approved', 'rejected']),
            }, depends=['state'])
    decision_date = fields.DateTime('Decision Date', states={
            'required': Eval('state').in_(['approved', 'rejected']),
            })

    @classmethod
    def __setup__(cls):
        super(Request, cls).__setup__()
        cls._transitions |= set((
                ('pending', 'approved'),
                ('pending', 'rejected'),
                ('pending', 'cancelled'),
                ))
        cls._buttons.update({
                'approve': {
                    'invisible': Eval('state') != 'pending',
                    },
                'reject': {
                    'invisible': Eval('state') != 'pending',
                    },
                'cancel': {
                    'invisible': Eval('state') != 'pending',
                    },
                })

    @staticmethod
    def _get_document():
        return []

    @classmethod
    def get_document(cls):
        Model = Pool().get('ir.model')
        models = cls._get_document()
        models = Model.search([
                ('model', 'in', models),
                ])
        return [(m.model, m.name) for m in models]

    @fields.depends('document')
    def on_change_with_model(self, name=None):
        Model = Pool().get('ir.model')
        if not self.document:
            return None
        model = str(self.document).split(',')[0]
        models = Model.search([('model', '=', model)], limit=1)
        if not models:
            return None
        return models[0].id

    @classmethod
    @ModelView.button
    @Workflow.transition('approved')
    def approve(cls, requests):
        User = Pool().get('res.user')
        user = User(Transaction().user)
        for request in requests:
            request.user = user
            request.decision_date = datetime.now()
        cls.save(requests)

    @classmethod
    @ModelView.button
    @Workflow.transition('rejected')
    def reject(cls, requests):
        User = Pool().get('res.user')
        user = User(Transaction().user)
        for request in requests:
            request.user = user
            request.decision_date = datetime.now()
        cls.save(requests)

    @classmethod
    @ModelView.button
    @Workflow.transition('cancelled')
    def cancel(cls, requests):
        pass