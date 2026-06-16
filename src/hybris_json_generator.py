"""
Gerador de JSONs para Vinculação de Pagamentos - Sistema Hybris v2.0
Compatível com n8n Code Node e execução local

VERSÃO 2.0 - MUDANÇAS:
- IDs e UUIDs com 42 caracteres alfanuméricos (sem traços)
- Aceita JSON de cabeçalho do Hybris como input
- Validação de campos obrigatórios do cabeçalho
- Campo numberOfQuotas obrigatório para crédito no formulário
- Status sempre "PAID" (não informado pelo usuário)
"""

from datetime import datetime
import json
from typing import Dict, List, Optional
import random
import string
from zoneinfo import ZoneInfo  # Python 3.9+
# Para Python 3.7-3.8, use: pip install backports.zoneinfo


class HybrisJSONGenerator:
    """Classe para gerar JSONs de transações para o sistema Hybris"""

    def __init__(self):
        # Usar timezone de São Paulo (Brasil) - considera horário de verão automaticamente
        self.brazil_tz = ZoneInfo("America/Sao_Paulo")
        self.current_timestamp = datetime.now(self.brazil_tz).isoformat()

    @staticmethod
    def generate_unique_id() -> str:
        """
        Gera um ID único de 42 caracteres alfanuméricos (sem traços)
        Formato: apenas letras minúsculas e números
        Exemplo: 4216b627fb0841ce8e5eb44eeda9b3b4aa26624a13d
        """
        # Gera 42 caracteres aleatórios (a-z e 0-9)
        chars = string.ascii_lowercase + string.digits
        unique_id = ''.join(random.choice(chars) for _ in range(42))
        return unique_id

    @staticmethod
    def format_money(value: float) -> int:
        """Converte valor em reais para centavos (inteiro)"""
        return int(value * 100)

    @staticmethod
    def parse_money(cents: int) -> float:
        """Converte centavos para reais"""
        return cents / 100

    def validate_header_json(self, header_json: Dict) -> tuple[bool, List[str]]:
        """
        Valida se o JSON do cabeçalho possui todos os campos obrigatórios

        Returns:
            tuple: (is_valid, list_of_errors)
        """
        errors = []
        required_fields = [
            "id", "items", "price", "number", "status",
            "reference", "created_at", "updated_at"
        ]

        # Validar campos raiz
        for field in required_fields:
            if field not in header_json:
                errors.append(f"Campo obrigatório ausente no cabeçalho: '{field}'")

        # Validar que items é um array e não está vazio
        if "items" in header_json:
            if not isinstance(header_json["items"], list):
                errors.append("Campo 'items' deve ser um array")
            elif len(header_json["items"]) == 0:
                errors.append("Campo 'items' não pode estar vazio")
            else:
                # Validar campos obrigatórios do primeiro item
                item_required = ["id", "sku", "name", "uuid", "quantity",
                               "created_at", "unit_price", "updated_at"]
                item = header_json["items"][0]
                for field in item_required:
                    if field not in item:
                        errors.append(f"Campo obrigatório ausente em items[0]: '{field}'")

        # Validar que price é numérico e positivo
        if "price" in header_json:
            if not isinstance(header_json["price"], (int, float)):
                errors.append("Campo 'price' deve ser numérico")
            elif header_json["price"] <= 0:
                errors.append("Campo 'price' deve ser maior que zero")

        # Validar status
        if "status" in header_json and header_json["status"] != "PAID":
            errors.append("Campo 'status' deve ser 'PAID'")

        is_valid = len(errors) == 0
        return is_valid, errors

    def create_pix_transaction(
        self,
        amount: int,
        merchant_name: str,
        merchant_code: str = "0027822336749400",
        terminal_number: str = "11111111",
        authorization_code: Optional[str] = None,
        created_at: Optional[str] = None,
        preserve_payment_fields: Optional[Dict] = None
    ) -> Dict:
        """Cria uma transação PIX

        Args:
            preserve_payment_fields: Se fornecido, preserva os campos originais do JSON colado
        """

        transaction_id = self.generate_unique_id()  # 42 chars, sem traços
        timestamp = created_at or self.current_timestamp
        auth_code = authorization_code or self.generate_unique_id()

        # Campos padrão
        default_payment_fields = {
            "v40Code": 0,
            "cityState": "Fake callback",
            "clientName": "Fake callback",
            "statusCode": 0,
            "hasPassword": False,
            "hasWarranty": False,
            "productName": "PIX PAGAMENTO",
            "requestDate": int(datetime.now().strftime("%y%m%d%H%M%S")),
            "documentType": "J",
            "hasSignature": False,
            "merchantCode": merchant_code,
            "merchantName": merchant_name,
            "applicationId": "cielo.launcher",
            "totalizerCode": 0,
            "isExternalCall": True,
            "numberOfQuotas": 0,
            "applicationName": "cielo.launcher.ORDER",
            "cardCaptureType": 0,
            "hasConnectivity": False,
            "merchantAddress": "RUA EXEMPLO",
            "paymentTypeCode": 0,
            "hasSentReference": False,
            "isFinancialProduct": True,
            "primaryProductCode": 25,
            "primaryProductName": "PIX",
            "hasSentMerchantCode": False,
            "paymentTransactionId": self.generate_unique_id(),
            "secondaryProductCode": 1,
            "secondaryProductName": "PAGAMENTO",
            "receiptPrintPermission": 0,
            "hasPrintedClientReceipt": False,
            "isDoubleFontPrintAllowed": False,
            "isOnlyIntegrationCancelable": False
        }

        # Se preserve_payment_fields foi fornecido, usar os valores originais
        if preserve_payment_fields:
            # Mesclar: preservar campos originais, mas atualizar merchantName se fornecido
            payment_fields = {**preserve_payment_fields}
            payment_fields["merchantName"] = merchant_name
            payment_fields["merchantCode"] = merchant_code
            # NÃO gerar novo paymentTransactionId - preservar o original
        else:
            payment_fields = default_payment_fields

        return {
            "id": transaction_id,
            "uuid": transaction_id,  # Mesmo valor que id
            "amount": amount,
            "number": terminal_number,
            "status": "CONFIRMED",
            "created_at": timestamp,
            "updated_at": timestamp,
            "description": "",
            "payment_fields": payment_fields,
            "terminal_number": terminal_number,
            "transaction_type": "PAYMENT",
            "authorization_code": auth_code
        }

    def create_debit_transaction(
        self,
        amount: int,
        merchant_name: str,
        card_mask: str = "************1234",
        card_brand: str = "VISA",
        merchant_code: str = "0011112591759400",
        terminal_number: str = "11111111",
        authorization_code: str = "123456",
        created_at: Optional[str] = None,
        preserve_payment_fields: Optional[Dict] = None,
        preserve_card: Optional[Dict] = None,
        preserve_external_id: Optional[str] = None
    ) -> Dict:
        """Cria uma transação de DÉBITO

        Args:
            preserve_payment_fields: Se fornecido, preserva os campos originais do JSON colado
        """

        transaction_id = self.generate_unique_id()  # 42 chars, sem traços
        timestamp = created_at or self.current_timestamp

        # Campos padrão
        default_payment_fields = {
            "pan": card_mask,
            "v40Code": 8,
            "typeName": "VENDA A DEBITO",
            "cityState": "NOVA LIMA MG",
            "clientName": "VINCULACAO MANUAL ",
            "serviceTax": 0,
            "statusCode": 1,
            "boardingTax": 0,
            "hasPassword": True,
            "hasWarranty": False,
            "productName": "DEBITO A VISTA",
            "requestDate": int(datetime.now().timestamp() * 1000),
            "changeAmount": 0,
            "documentType": "J",
            "entranceMode": "602010107080",
            "hasSignature": False,
            "merchantCode": merchant_code,
            "merchantName": merchant_name,
            "applicationId": "cielo.launcher",
            "totalizerCode": 81,
            "upFrontAmount": 0,
            "creditAdminTax": 0,
            "firstQuotaDate": 0,
            "interestAmount": 0,
            "isExternalCall": True,
            "numberOfQuotas": 0,
            "applicationName": "cielo.launcher.ORDER",
            "avaiableBalance": 0,
            "cardCaptureType": 0,
            "finalCryptogram": "035B9C580BE66A6B",
            "hasConnectivity": True,
            "merchantAddress": "RUA OROZIMBO NONATO",
            "paymentTypeCode": 1,
            "firstQuotaAmount": 0,
            "hasSentReference": False,
            "isFinancialProduct": True,
            "primaryProductCode": 2000,
            "primaryProductName": "DEBITO",
            "hasSentMerchantCode": False,
            "cardLabelApplication": "Debit",
            "paymentTransactionId": self.generate_unique_id(),
            "secondaryProductCode": 1,
            "secondaryProductName": "A VISTA",
            "originalTransactionId": "0",
            "receiptPrintPermission": 1,
            "hasPrintedClientReceipt": False,
            "isDoubleFontPrintAllowed": False,
            "isOnlyIntegrationCancelable": False
        }

        # Se preserve_payment_fields foi fornecido, usar os valores originais
        if preserve_payment_fields:
            payment_fields = {**preserve_payment_fields}
            payment_fields["merchantName"] = merchant_name
            payment_fields["merchantCode"] = merchant_code
            # NÃO gerar novo paymentTransactionId - preservar o original
        else:
            payment_fields = default_payment_fields

        # Preservar card se fornecido, senão usar padrão
        card_obj = preserve_card if preserve_card else {
            "mask": card_mask,
            "brand": card_brand
        }

        # Preservar external_id se fornecido, senão gerar novo
        ext_id = preserve_external_id if preserve_external_id else self.generate_unique_id()

        return {
            "id": transaction_id,
            "card": card_obj,
            "uuid": transaction_id,  # Mesmo valor que id
            "amount": amount,
            "number": terminal_number,
            "status": "CONFIRMED",
            "created_at": timestamp,
            "updated_at": timestamp,
            "description": "",
            "external_id": ext_id,
            "payment_fields": payment_fields,
            "terminal_number": terminal_number,
            "terminal_hardware_model": "L3",
            "terminal_hardware_manufacturer": "Quantum",
            "transaction_type": "PAYMENT",
            "authorization_code": authorization_code
        }

    def create_credit_transaction(
        self,
        amount: int,
        merchant_name: str,
        number_of_quotas: int = 1,
        card_mask: str = "************1234",
        card_brand: str = "MASTERCARD",
        merchant_code: str = "0011112591759400",
        terminal_number: str = "11111111",
        authorization_code: str = "123456",
        created_at: Optional[str] = None,
        preserve_payment_fields: Optional[Dict] = None,
        preserve_card: Optional[Dict] = None,
        preserve_external_id: Optional[str] = None
    ) -> Dict:
        """Cria uma transação de CRÉDITO

        Args:
            preserve_payment_fields: Se fornecido, preserva os campos originais do JSON colado
        """

        transaction_id = self.generate_unique_id()  # 42 chars, sem traços
        timestamp = created_at or self.current_timestamp

        # Ajustar descrições baseado no número de parcelas
        description = f"PARCELADO LOJA EM {number_of_quotas:02d} PARCELAS" if number_of_quotas > 1 else "A VISTA"
        product_name = "CREDITO PARCELADO LOJA" if number_of_quotas > 1 else "CREDITO A VISTA"
        secondary_name = "PARCELADO LOJA" if number_of_quotas > 1 else "A VISTA"
        secondary_code = 2 if number_of_quotas > 1 else 1

        # Campos padrão
        default_payment_fields = {
            "pan": card_mask,
            "v40Code": 6,
            "typeName": "VENDA A CREDITO",
            "cityState": "NOVA LIMA MG",
            "clientName": "VINCULACAO MANUAL ",
            "serviceTax": 0,
            "statusCode": 1,
            "boardingTax": 0,
            "hasPassword": True,
            "hasWarranty": False,
            "productName": product_name,
            "requestDate": int(datetime.now().timestamp() * 1000),
            "changeAmount": 0,
            "documentType": "J",
            "entranceMode": "603010107080",
            "hasSignature": False,
            "merchantCode": merchant_code,
            "merchantName": merchant_name,
            "applicationId": "cielo.launcher",
            "totalizerCode": 80,
            "upFrontAmount": 0,
            "creditAdminTax": 0,
            "firstQuotaDate": 0,
            "interestAmount": 0,
            "isExternalCall": True,
            "numberOfQuotas": number_of_quotas,
            "applicationName": "cielo.launcher.ORDER",
            "avaiableBalance": 0,
            "cardCaptureType": 0,
            "finalCryptogram": "7E50088A9AE3FE7E",
            "hasConnectivity": True,
            "merchantAddress": "RUA OROZIMBO NONATO",
            "paymentTypeCode": 1,
            "firstQuotaAmount": 0,
            "hasSentReference": False,
            "isFinancialProduct": True,
            "primaryProductCode": 1000,
            "primaryProductName": "CREDITO",
            "hasSentMerchantCode": False,
            "cardLabelApplication": "Credit",
            "paymentTransactionId": self.generate_unique_id(),
            "secondaryProductCode": secondary_code,
            "secondaryProductName": secondary_name,
            "originalTransactionId": "0",
            "receiptPrintPermission": 1,
            "hasPrintedClientReceipt": False,
            "isDoubleFontPrintAllowed": False,
            "isOnlyIntegrationCancelable": False
        }

        # Se preserve_payment_fields foi fornecido, usar os valores originais
        if preserve_payment_fields:
            payment_fields = {**preserve_payment_fields}
            payment_fields["merchantName"] = merchant_name
            payment_fields["merchantCode"] = merchant_code
            payment_fields["numberOfQuotas"] = number_of_quotas
            # NÃO gerar novo paymentTransactionId - preservar o original
        else:
            payment_fields = default_payment_fields

        # Preservar card se fornecido, senão usar padrão
        card_obj = preserve_card if preserve_card else {
            "mask": card_mask,
            "brand": card_brand
        }

        # Preservar external_id se fornecido, senão gerar novo
        ext_id = preserve_external_id if preserve_external_id else self.generate_unique_id()

        return {
            "id": transaction_id,
            "card": card_obj,
            "uuid": transaction_id,  # Mesmo valor que id
            "amount": amount,
            "number": terminal_number,
            "status": "CONFIRMED",
            "created_at": timestamp,
            "updated_at": timestamp,
            "description": description,
            "external_id": ext_id,
            "payment_fields": payment_fields,
            "terminal_number": terminal_number,
            "terminal_hardware_model": "L3",
            "terminal_hardware_manufacturer": "Quantum",
            "transaction_type": "PAYMENT",
            "authorization_code": authorization_code
        }

    def validate_transaction_totals(self, complete_order: Dict) -> Dict:
        """
        Valida se a soma das transações bate com o valor total do cabeçalho.
        Se houver diferença, ajusta automaticamente o price do cabeçalho
        para bater com a soma real das transações (evita rejeição pela API).

        Retorna dict com informações do ajuste:
        {
            "adjusted": bool,
            "original_price": int,
            "transactions_total": int,
            "difference": int
        }
        """
        header_price = complete_order["price"]
        transactions_total = sum(t["amount"] for t in complete_order["transactions"])
        difference = abs(header_price - transactions_total)

        result = {
            "adjusted": False,
            "original_price": header_price,
            "transactions_total": transactions_total,
            "difference": difference
        }

        if header_price != transactions_total:
            print(f"[auto-fix] Price ajustado: {header_price} → {transactions_total} (diferença: {difference} centavos)")
            complete_order["price"] = transactions_total
            # Ajustar também unit_price do item para manter consistência
            if complete_order.get("items") and len(complete_order["items"]) > 0:
                complete_order["items"][0]["unit_price"] = transactions_total
            result["adjusted"] = True

        return result

    def generate_json_with_header(
        self,
        header_json: Dict,
        transaction_type: str,
        transactions_data: List[Dict]
    ) -> str:
        """
        Gera o JSON completo baseado no cabeçalho fornecido e dados das transações

        Args:
            header_json: JSON do cabeçalho obtido do Hybris (com id, items, price, etc.)
            transaction_type: "PIX", "DEBITO", "CREDITO" ou "MULTIPLAS"
            transactions_data: Lista com dados das transações

        Returns:
            String JSON formatada ou dict com erro
        """

        # Validar cabeçalho
        is_valid, errors = self.validate_header_json(header_json)
        if not is_valid:
            return {
                "success": False,
                "error": "Cabeçalho JSON inválido",
                "validation_errors": errors
            }

        # Criar cópia do cabeçalho
        complete_order = header_json.copy()

        # Garantir que status seja PAID
        complete_order["status"] = "PAID"

        # Inicializar array de transactions
        complete_order["transactions"] = []

        # Processar transações baseado no tipo
        transaction_type = transaction_type.upper()

        if transaction_type == "PIX":
            for trans_data in transactions_data:
                transaction = self.create_pix_transaction(
                    amount=self.format_money(trans_data.get("amount", 0)),
                    merchant_name=trans_data.get("merchant_name", ""),
                    merchant_code=trans_data.get("merchant_code", "0027822336749400"),
                    terminal_number=trans_data.get("number", trans_data.get("terminal_number", "11111111")),
                    authorization_code=trans_data.get("authorization_code"),
                    created_at=trans_data.get("created_at"),
                    preserve_payment_fields=trans_data.get("preserve_payment_fields")
                )
                complete_order["transactions"].append(transaction)

        elif transaction_type == "DEBITO":
            for trans_data in transactions_data:
                transaction = self.create_debit_transaction(
                    amount=self.format_money(trans_data.get("amount", 0)),
                    merchant_name=trans_data.get("merchant_name", ""),
                    card_mask=trans_data.get("card_mask", "************1234"),
                    card_brand=trans_data.get("card_brand", "VISA"),
                    merchant_code=trans_data.get("merchant_code", "0011112591759400"),
                    terminal_number=trans_data.get("number", trans_data.get("terminal_number", "11111111")),
                    authorization_code=trans_data.get("authorization_code", "123456"),
                    created_at=trans_data.get("created_at"),
                    preserve_payment_fields=trans_data.get("preserve_payment_fields"),
                    preserve_card=trans_data.get("preserve_card"),
                    preserve_external_id=trans_data.get("preserve_external_id")
                )
                complete_order["transactions"].append(transaction)

        elif transaction_type == "CREDITO":
            for trans_data in transactions_data:
                transaction = self.create_credit_transaction(
                    amount=self.format_money(trans_data.get("amount", 0)),
                    merchant_name=trans_data.get("merchant_name", ""),
                    number_of_quotas=trans_data.get("number_of_quotas", 1),
                    card_mask=trans_data.get("card_mask", "************1234"),
                    card_brand=trans_data.get("card_brand", "MASTERCARD"),
                    merchant_code=trans_data.get("merchant_code", "0011112591759400"),
                    terminal_number=trans_data.get("number", trans_data.get("terminal_number", "11111111")),
                    authorization_code=trans_data.get("authorization_code", "123456"),
                    created_at=trans_data.get("created_at"),
                    preserve_payment_fields=trans_data.get("preserve_payment_fields"),
                    preserve_card=trans_data.get("preserve_card"),
                    preserve_external_id=trans_data.get("preserve_external_id")
                )
                complete_order["transactions"].append(transaction)

        elif transaction_type == "MULTIPLAS":
            # Para múltiplas transações, processar cada uma individualmente
            for trans_data in transactions_data:
                t_type = trans_data.get("type", "").upper()

                # Se não tem tipo, tentar detectar a partir dos dados do JSON colado
                if not t_type and "payment_fields" in trans_data:
                    product_code = trans_data["payment_fields"].get("primaryProductCode", 25)
                    if product_code == 25:
                        t_type = "PIX"
                    elif product_code == 2000:
                        t_type = "DEBITO"
                    elif product_code == 1000:
                        t_type = "CREDITO"

                t_amount = self.format_money(trans_data.get("amount", 0))

                if t_type == "PIX":
                    trans = self.create_pix_transaction(
                        amount=t_amount,
                        merchant_name=trans_data.get("merchant_name", ""),
                        merchant_code=trans_data.get("merchant_code", "0027822336749400"),
                        terminal_number=trans_data.get("number", trans_data.get("terminal_number", "11111111")),
                        authorization_code=trans_data.get("authorization_code"),
                        preserve_payment_fields=trans_data.get("preserve_payment_fields")
                    )
                elif t_type == "DEBITO":
                    trans = self.create_debit_transaction(
                        amount=t_amount,
                        merchant_name=trans_data.get("merchant_name", ""),
                        card_mask=trans_data.get("card_mask", "************1234"),
                        card_brand=trans_data.get("card_brand", "VISA"),
                        merchant_code=trans_data.get("merchant_code", "0011112591759400"),
                        terminal_number=trans_data.get("number", trans_data.get("terminal_number", "11111111")),
                        authorization_code=trans_data.get("authorization_code", "123456"),
                        preserve_payment_fields=trans_data.get("preserve_payment_fields"),
                        preserve_card=trans_data.get("preserve_card"),
                        preserve_external_id=trans_data.get("preserve_external_id")
                    )
                elif t_type == "CREDITO":
                    trans = self.create_credit_transaction(
                        amount=t_amount,
                        merchant_name=trans_data.get("merchant_name", ""),
                        number_of_quotas=trans_data.get("number_of_quotas", 1),
                        card_mask=trans_data.get("card_mask", "************1234"),
                        card_brand=trans_data.get("card_brand", "MASTERCARD"),
                        merchant_code=trans_data.get("merchant_code", "0011112591759400"),
                        terminal_number=trans_data.get("number", trans_data.get("terminal_number", "11111111")),
                        authorization_code=trans_data.get("authorization_code", "123456"),
                        preserve_payment_fields=trans_data.get("preserve_payment_fields"),
                        preserve_card=trans_data.get("preserve_card"),
                        preserve_external_id=trans_data.get("preserve_external_id")
                    )
                else:
                    continue

                complete_order["transactions"].append(trans)

        # Validar e ajustar totais automaticamente
        adjustment = self.validate_transaction_totals(complete_order)

        return json.dumps(complete_order, indent=2, ensure_ascii=False)


# ============================================
# FUNÇÃO PARA USO NO N8N
# ============================================

def n8n_generate_json(input_data: Dict) -> Dict:
    """
    Função compatível com o Code Node do n8n - VERSÃO 2.0

    Input esperado (input_data):
    {
        "header_json": { ... },  # JSON do cabeçalho obtido do Hybris
        "transaction_type": "PIX|DEBITO|CREDITO|MULTIPLAS",
        "transactions": [
            {
                "amount": 100.50,
                "merchant_name": "Loja X",
                "card_mask": "************1234",  # para débito/crédito
                "card_brand": "VISA",               # para débito/crédito
                "number_of_quotas": 6,              # para crédito
                "authorization_code": "ABC123"      # para débito/crédito
            }
        ]
    }

    Returns:
        Dict com o JSON gerado e metadados ou erro
    """
    try:
        generator = HybrisJSONGenerator()

        # Extrair dados do input
        header_json = input_data.get("header_json", {})
        transaction_type = input_data.get("transaction_type", "")
        transactions_data = input_data.get("transactions", [])

        # Validar inputs básicos
        if not header_json:
            return {
                "success": False,
                "error": "Campo 'header_json' não fornecido"
            }

        if not transaction_type:
            return {
                "success": False,
                "error": "Campo 'transaction_type' não fornecido"
            }

        if not transactions_data or len(transactions_data) == 0:
            return {
                "success": False,
                "error": "Campo 'transactions' vazio ou não fornecido"
            }

        # Gerar JSON
        json_result = generator.generate_json_with_header(
            header_json=header_json,
            transaction_type=transaction_type,
            transactions_data=transactions_data
        )

        # Verificar se houve erro na validação
        if isinstance(json_result, dict) and not json_result.get("success", True):
            return json_result

        # Parse do JSON gerado
        json_object = json.loads(json_result)

        return {
            "success": True,
            "message": "JSON gerado com sucesso!",
            "order_number": json_object["number"],
            "transaction_count": len(json_object["transactions"]),
            "total_amount": json_object["price"],
            "total_amount_brl": generator.parse_money(json_object["price"]),
            "json_string": json_result,
            "json_object": json_object
        }

    except json.JSONDecodeError as e:
        return {
            "success": False,
            "error": "Erro ao fazer parse do JSON do cabeçalho",
            "details": str(e)
        }

    except Exception as e:
        return {
            "success": False,
            "error": "Erro ao gerar JSON",
            "details": str(e),
            "input_received": input_data
        }


# ============================================
# EXEMPLOS DE USO
# ============================================

def exemplo_pix_com_header():
    """Exemplo: Gerar JSON PIX com cabeçalho do Hybris"""
    generator = HybrisJSONGenerator()

    # Cabeçalho que viria do formulário (copiado do Hybris)
    header = {
        "id": "c777434f-a679-4298-9803-12d069a4a13d",
        "items": [{
            "id": 1186914740,
            "sku": "08389316",
            "name": "Leandro teixeira Filipe",
            "uuid": "fedcb39b09d9495194158b5a88522662",
            "details": None,
            "order_id": 3741538564,
            "quantity": 1,
            "sku_type": None,
            "reference": None,
            "created_at": "2022-09-09T14:58:12Z",
            "unit_price": 599000,
            "updated_at": "2022-09-09T14:58:12Z",
            "description": None,
            "unit_of_measure": "EACH"
        }],
        "price": 599000,
        "number": "08389316",
        "status": "PAID",
        "reference": "Leandro teixeira Filipe",
        "created_at": "2022-09-09T14:58:12Z",
        "updated_at": "2022-09-09T14:58:12Z"
    }

    # Dados da transação PIX do formulário
    transactions = [{
        "amount": 5990.00,  # em reais
        "merchant_name": "Loja Exemplo LTDA"
    }]

    json_output = generator.generate_json_with_header(
        header_json=header,
        transaction_type="PIX",
        transactions_data=transactions
    )

    print("=" * 50)
    print("EXEMPLO PIX COM CABEÇALHO")
    print("=" * 50)
    print(json_output)
    return json_output


def exemplo_credito_com_header():
    """Exemplo: Gerar JSON Crédito Parcelado com cabeçalho"""
    generator = HybrisJSONGenerator()

    header = {
        "id": "c777434f-a679-4298-9803-12d069a4a13d",
        "items": [{
            "id": 1186914740,
            "sku": "08389316",
            "name": "Leandro teixeira Filipe",
            "uuid": "fedcb39b09d9495194158b5a88522662",
            "details": None,
            "order_id": 3741538564,
            "quantity": 1,
            "sku_type": None,
            "reference": None,
            "created_at": "2022-09-09T14:58:12Z",
            "unit_price": 599000,
            "updated_at": "2022-09-09T14:58:12Z",
            "description": None,
            "unit_of_measure": "EACH"
        }],
        "price": 599000,
        "number": "08389316",
        "status": "PAID",
        "reference": "Leandro teixeira Filipe",
        "created_at": "2022-09-09T14:58:12Z",
        "updated_at": "2022-09-09T14:58:12Z"
    }

    transactions = [{
        "amount": 5990.00,
        "merchant_name": "Loja Exemplo LTDA",
        "number_of_quotas": 6,  # OBRIGATÓRIO para crédito
        "card_mask": "************9012",
        "card_brand": "MASTERCARD",
        "authorization_code": "XYZ789"
    }]

    json_output = generator.generate_json_with_header(
        header_json=header,
        transaction_type="CREDITO",
        transactions_data=transactions
    )

    print("\n" + "=" * 50)
    print("EXEMPLO CRÉDITO PARCELADO COM CABEÇALHO")
    print("=" * 50)
    print(json_output)
    return json_output


if __name__ == "__main__":
    # Executar exemplos
    print("TESTANDO GERADOR V2.0 COM IDs DE 42 CARACTERES\n")

    # Testar geração de ID
    gen = HybrisJSONGenerator()
    print("Teste de ID único:")
    id1 = gen.generate_unique_id()
    id2 = gen.generate_unique_id()
    print(f"  ID 1: {id1} (tamanho: {len(id1)})")
    print(f"  ID 2: {id2} (tamanho: {len(id2)})")
    print(f"  São diferentes: {id1 != id2}\n")

    # Executar exemplos
    exemplo_pix_com_header()
    exemplo_credito_com_header()
