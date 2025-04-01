from marshmallow import Schema, fields


class AddReimbursementWalletBankAccountSchema(Schema):
    BankAcctName = fields.String()
    BankAccount = fields.String()
    BankRoutingNumber = fields.String()
    BankAccountTypeCode = fields.String()
