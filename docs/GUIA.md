# Guia de Uso - Gerador JSON Hybris

**Versão**: 2.0
**Última atualização**: 2025-12-09

---

## 🚀 Início Rápido

### 1. Acessar a Aplicação
Abra no navegador: **https://gerajson.sensebike.com.br**

### 2. Fazer Login
Use suas credenciais fornecidas pelo administrador.

### 3. Gerar JSON
Siga os 3 passos abaixo.

---

## 📖 Como Usar o Sistema

### PASSO 1: Obter JSON do Cabeçalho no Hybris

No sistema Hybris, copie **TODO o JSON do pedido ATÉ ANTES do campo "transactions"**.

**Importante:** O cabeçalho termina antes de `"transactions"`. Exemplo:

```json
{
  "id" : "c777434f-a679-4298-9803-12d069a4a13d",
  "items" : [ {
    "id" : 1186914740,
    "sku" : "08389316",
    "name" : "Leandro teixeira Filipe",
    "uuid" : "fedcb39b-09d9-4951-9415-8b5a88522662",
    "details" : null,
    "order_id" : 3741538564,
    "quantity" : 1,
    "sku_type" : null,
    "reference" : null,
    "created_at" : "2022-09-09T14:58:12Z",
    "unit_price" : 599000,
    "updated_at" : "2022-09-09T14:58:12Z",
    "description" : null,
    "unit_of_measure" : "EACH"
  } ],
  "price" : 599000,
  "number" : "08389316",
  "status" : "PAID",
  "reference" : "Leandro teixeira Filipe",
  "created_at" : "2022-09-09T14:58:12Z",
  "updated_at" : "2022-09-09T14:58:12Z"
  ← COPIE ATÉ AQUI (antes de "transactions")
}
```

**Não copie:** O campo `"transactions"` será gerado automaticamente pelo sistema.

---

### PASSO 2: Preencher Formulário Web

1. **Cole o JSON** no campo de texto grande
2. **Preencha o MerchantName** (já vem pré-preenchido com seu nome)
3. **Selecione o tipo** de transação
4. **Preencha os campos** (aparecem automaticamente)
5. **Clique em "Gerar JSON"**

---

### PASSO 3: Usar o JSON Gerado

- **Copiar**: Ctrl+A → Ctrl+C no preview
- **Baixar**: Botão "Baixar JSON"
- **Usar**: Cole no Postman e envie para API

---

## 🔧 Tipos de Transação

### PIX
**Campos obrigatórios:**
- ✅ **amount** - Valor em Reais (ex: 5990.00)
- ✅ **number** - Número da transação/terminal
- ✅ **merchantName** - Nome do estabelecimento (pré-preenchido)

**Campos opcionais:**
- ○ **authorization_code** - Código de autorização

---

### DÉBITO
**Campos obrigatórios:**
- ✅ **amount** - Valor em Reais
- ✅ **number** - Número da transação/terminal
- ✅ **merchantName** - Nome do estabelecimento (pré-preenchido)
- ✅ **authorization_code** - Código de autorização

**Campos automáticos** (não requer preenchimento):
- 🔒 **card.mask** - Fixo: "************XXXX"
- 🔒 **card.brand** - Fixo: "XXXXXXXX"

---

### CRÉDITO
**Campos obrigatórios:**
- ✅ **amount** - Valor em Reais
- ✅ **number** - Número da transação/terminal
- ✅ **merchantName** - Nome do estabelecimento (pré-preenchido)
- ✅ **numberOfQuotas** - Número de parcelas (1-24)
- ✅ **authorization_code** - Código de autorização

**Campos automáticos:**
- 🔒 **card.mask** - Fixo: "************XXXX"
- 🔒 **card.brand** - Fixo: "XXXXXXXX"

---

### MÚLTIPLAS TRANSAÇÕES

Para cada transação:
1. Escolha o tipo (PIX/DÉBITO/CRÉDITO)
2. Preencha campos específicos (conforme acima)
3. **Importante:** Soma das transações = price do cabeçalho

**Exemplo:**
- Transação 1 (DÉBITO): R$ 2.752,72
- Transação 2 (CRÉDITO): R$ 3.237,28
- **Total**: R$ 5.990,00 ✅

---

## ✅ Validações Automáticas

O sistema valida:
- ✅ JSON do cabeçalho válido
- ✅ Campos obrigatórios preenchidos
- ✅ Soma das transações = valor total (múltiplas)
- ✅ Parcelas entre 1-24 (crédito)
- ✅ Valores numéricos

Erros aparecem em **vermelho** na tela.

---

## 📋 Exemplos Práticos

### Exemplo 1: PIX de R$ 5.990,00

**Entrada:**
- Tipo: PIX
- Valor: R$ 5.990,00
- Number: 1111111
- MerchantName: Fake callback - Kennedy -

**Saída (campo transactions):**
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
    "merchantName": "Fake callback - Kennedy -",
    ...
  }
}]
```

---

### Exemplo 2: CRÉDITO 6x de R$ 5.990,00

**Entrada:**
- Tipo: CRÉDITO
- Valor: R$ 5.990,00
- Number: 616755
- Parcelas: 6
- Código Auth: 859005

**Saída:**
```json
"transactions": [{
  "id": "xyz123...",
  "card": {
    "mask": "************XXXX",
    "brand": "XXXXXXXX"
  },
  "amount": 599000,
  "description": "PARCELADO LOJA EM 06 PARCELAS",
  "payment_fields": {
    "primaryProductCode": 1000,
    "primaryProductName": "CREDITO",
    "productName": "CREDITO PARCELADO LOJA",
    "numberOfQuotas": 6,
    ...
  },
  "authorization_code": "859005"
}]
```

**Ver mais exemplos:** Pasta [`examples/`](../examples/)

---

## 👥 Gerenciar Usuários

### Adicionar Novo Usuário

1. Faça login com uma conta **admin**
2. Clique na aba **"👥 Gerenciar Usuários"**
3. Preencha os campos:
   - Username (ex: joao.silva)
   - Email
   - Nome completo
   - Senha (mínimo 8 caracteres)
   - **Nome para MerchantName** (ex: João) - Opcional
4. Clique em **"✅ Criar Usuário"**

---

### Editar MerchantName

O MerchantName padrão de cada usuário pode ser personalizado:

1. Vá para aba **"✏️ Editar MerchantName"**
2. Selecione o usuário
3. Digite o novo nome (ex: "Kennedy", "Alisson")
4. Clique em **"✅ Salvar"**

**Resultado:** O usuário terá `"Fake callback - Kennedy - "` pré-preenchido automaticamente.

**Dica:** Use o botão **🔄 Resetar** no campo MerchantName para recarregar o valor do seu perfil.

---

### Remover Usuário

1. Vá para **"👥 Gerenciar Usuários"**
2. Selecione o usuário na lista
3. Clique em **"🗑️ Remover Usuário"**
4. Confirme a ação

---

## 💡 Dicas de Uso

1. **Sempre copie o JSON completo** do Hybris (até antes de "transactions")
2. **Verifique os valores** antes de gerar
3. **Use o preview** para conferir antes de copiar
4. **Salve o JSON** para histórico (botão download)
5. **Em MÚLTIPLAS, confira a soma** dos valores

---

## 🎯 Campos Importantes

### MerchantName
- **Formato**: `"Fake callback - [Nome] - "`
- **Personalização**: Use a aba "✏️ Editar MerchantName" para definir seu nome
- **Uso**: Pode adicionar texto após o nome padrão (ex: "Fake callback - Kennedy - RE: Pedido 12345")

### Valores Monetários
- **No cabeçalho (Hybris):** Sempre em centavos (599000 = R$ 5.990,00)
- **No formulário (app):** Em Reais (5990.00)
- **Sistema converte automaticamente**

### IDs
- **42 caracteres** alfanuméricos
- **Sem traços**
- **Gerados automaticamente**
- **id = uuid** (sempre iguais)

### Card Mask
- **Formato:** `************XXXX`
- **Preenchido automaticamente** (não precisa editar)

### Número de Parcelas
- **Mínimo:** 1 (à vista)
- **Máximo:** 24
- **Obrigatório** para crédito

---

## 🔄 Fluxo Completo

```
Hybris → Copiar JSON (sem "transactions")
  ↓
Streamlit App → Colar + Preencher campos
  ↓
Gerar JSON → Preview com "transactions"
  ↓
Copiar ou Baixar
  ↓
Postman → Enviar para API
  ↓
Vinculação Concluída ✅
```

---

## 📞 Precisa de Ajuda?

**Problemas de login?** → Ver [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

**Exemplos de JSON?** → Ver pasta [`examples/`](../examples/)

**Dúvidas sobre campos?** → Leia as seções acima sobre cada tipo de transação

---

**Tempo estimado de uso:** < 1 minuto por JSON
**Dificuldade:** Fácil 🟢
**Requer conhecimento técnico:** Não ❌
