# Exemplos de Uso

Exemplos práticos para cada tipo de transação.

---

## 📁 Arquivos de Exemplo

Exemplos completos de JSON estão em: `examples/`

- `exemplo_pix.txt` - Transação PIX
- `exemplo_debito.txt` - Transação Débito
- `exemplo_credito.txt` - Transação Crédito parcelado
- `exemplo_multiplas.txt` - Múltiplas transações

---

## 💡 Exemplo 1: PIX

### Entrada (Formulário):

**JSON do Cabeçalho:**
```json
{
  "id": "c777434f-a679-4298-9803-12d069a4a13d",
  "items": [{
    "id": 1186914740,
    "sku": "08389316",
    "name": "Leandro teixeira Filipe",
    "uuid": "fedcb39b09d9495194158b5a88522662",
    "quantity": 1,
    "unit_price": 599000,
    ...
  }],
  "price": 599000,
  "number": "08389316",
  "status": "PAID",
  ...
}
```

**Dados da Transação:**
- Tipo: PIX
- Valor: R$ 5.990,00
- Number: 1111111
- Estabelecimento: Fake callback Bruno

### Saída (JSON Gerado):

O campo `transactions` será adicionado com:
```json
"transactions": [{
  "id": "a0jgooopiimskgfjl94jh2id31q6q60ymfhxruzpfn",
  "uuid": "a0jgooopiimskgfjl94jh2id31q6q60ymfhxruzpfn",
  "amount": 599000,
  "number": "1111111",
  "status": "CONFIRMED",
  "payment_fields": {
    "primaryProductCode": 25,
    "primaryProductName": "PIX",
    "merchantName": "Fake callback Bruno",
    ...
  }
}]
```

---

## 💳 Exemplo 2: DÉBITO

### Entrada:

**Dados da Transação:**
- Tipo: DÉBITO
- Valor: R$ 5.990,00
- Number: 11111111
- Estabelecimento: Loja Exemplo
- Card Mask: ************1234
- Card Brand: VISA
- Código Auth: 11111111

### Saída:

```json
"transactions": [{
  "id": "xyz123...",
  "card": {
    "mask": "************1234",
    "brand": "VISA"
  },
  "amount": 599000,
  "payment_fields": {
    "primaryProductCode": 2000,
    "primaryProductName": "DEBITO",
    "productName": "DEBITO A VISTA",
    "numberOfQuotas": 0,
    ...
  },
  "authorization_code": "11111111"
}]
```

---

## 💰 Exemplo 3: CRÉDITO Parcelado

### Entrada:

**Dados da Transação:**
- Tipo: CRÉDITO
- Valor: R$ 5.990,00
- Number: 616755
- Estabelecimento: Fake callback Bruno
- **Parcelas: 4**
- Card Mask: ************9012
- Card Brand: MASTERCARD
- Código Auth: 859005

### Saída:

```json
"transactions": [{
  "id": "abc456...",
  "card": {
    "mask": "************9012",
    "brand": "MASTERCARD"
  },
  "amount": 599000,
  "description": "PARCELADO LOJA EM 04 PARCELAS",
  "payment_fields": {
    "primaryProductCode": 1000,
    "primaryProductName": "CREDITO",
    "productName": "CREDITO PARCELADO LOJA",
    "numberOfQuotas": 4,
    "secondaryProductName": "PARCELADO LOJA",
    ...
  },
  "authorization_code": "859005"
}]
```

---

## 🔀 Exemplo 4: MÚLTIPLAS TRANSAÇÕES

### Entrada:

**Transação 1 (DÉBITO):**
- Valor: R$ 2.752,72
- Number: 11111111
- Card: ************1111
- Brand: VISA
- Auth: AUTH001

**Transação 2 (CRÉDITO):**
- Valor: R$ 3.237,28
- Number: 616755
- Parcelas: 4
- Card: ************2222
- Brand: MASTERCARD
- Auth: AUTH002

**IMPORTANTE:** R$ 2.752,72 + R$ 3.237,28 = R$ 5.990,00 (price do cabeçalho)

### Saída:

```json
"transactions": [
  {
    "id": "trans1id...",
    "card": {"mask": "************1111", "brand": "VISA"},
    "amount": 275272,
    "payment_fields": {
      "primaryProductCode": 2000,
      "primaryProductName": "DEBITO",
      ...
    }
  },
  {
    "id": "trans2id...",
    "card": {"mask": "************2222", "brand": "MASTERCARD"},
    "amount": 323728,
    "payment_fields": {
      "primaryProductCode": 1000,
      "primaryProductName": "CREDITO",
      "numberOfQuotas": 4,
      ...
    }
  }
]
```

---

## 🎯 Dicas Importantes

### Valores Monetários
- **No cabeçalho:** Sempre em centavos (599000 = R$ 5.990,00)
- **No formulário:** Em Reais (5990.00)
- **Sistema converte automaticamente**

### IDs
- **42 caracteres** alfanuméricos
- **Sem traços**
- **Gerados automaticamente**
- **id = uuid** (sempre iguais)

### Timestamps
- **Timezone do Brasil** (America/Sao_Paulo)
- **Formato:** ISO 8601 com timezone
- **Exemplo:** `2025-10-27T10:30:45-03:00`

### Card Mask
- **Formato:** `************XXXX`
- **12 asteriscos** + 4 últimos dígitos
- **Exemplo:** `************1234`

### Número de Parcelas
- **Mínimo:** 1 (à vista)
- **Máximo:** 24
- **Obrigatório** para crédito

---

## ✅ Checklist de Validação

Antes de enviar para API, verifique:
- [ ] JSON do cabeçalho completo
- [ ] Campos obrigatórios preenchidos
- [ ] Soma das transações = price
- [ ] Card mask no formato correto (************XXXX)
- [ ] Parcelas entre 1-24 (se crédito)
- [ ] Status = "PAID"

---

## 🔗 Ver Exemplos Completos

Consulte os arquivos em `examples/` para JSONs completos gerados pelo sistema.

---

**Precisa de mais exemplos?** Entre em contato com o suporte.
