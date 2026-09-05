# EVIDÊNCIA — B5: Motor de Otimização e Pacing

**Data:** 04/09/2026
**Projeto:** CAMPAIA (F&M Tecnologia)
**Diretor:** Fábio Aluizio da Silva
**Bloco técnico:** B5 — Motor de otimização e pacing (Fase 3 do painel de execução)

---

## 1. Autorização do Diretor

Após o fechamento do P-19 (ver `EVIDENCIA_P19_FIX_20260904.md`), foi apresentado ao Diretor um conjunto de opções para o próximo bloco a construir (B5, B7, B8), com B5 marcado como recomendação. O Diretor respondeu, em mensagem literal:

> **"siga sua recomendação"**

Isto autoriza o início da construção do B5 — motor de otimização e pacing.

---

## 2. Ambiguidade de escopo encontrada e resolvida antes de escrever código

Antes de escrever qualquer código, uma pesquisa foi delegada para verificar se "motor de otimização" já tinha alguma especificação registrada em algum documento do projeto. Essa pesquisa encontrou uma árvore de documentação de produto até então não consultada nesta sessão, em `/home/claude/campaia/docs/product/`, com dois documentos relevantes:

### 2.1 `FUNCTIONAL_REQUIREMENTS.md` (linhas 253–271)

Este documento registra dois requisitos distintos sob o tema "F8 — Otimizações":

> **F8.1 "Sugerir otimizações"** (Ator: Sistema/Performance Agent)
> - "Aumentar budget se CTR > 2%"
> - "Pausar se CPA > limite"
> - "Ajustar lances se não atingir volume"
> - "Expandir público se CPC muito alto"
> — Status: 💭 Proposta (Fase 2 de produto)

> **F8.2 "Executar otimizações automáticas"** (Ator: Sistema/Policy autoriza)
> - "Ajustes de baixo risco (ajuste de lance <5%, mudança de bid strategy)"
> - "Requer aprovação para mudanças maiores"
> — Status: **❌ Out of scope MVP (Fase 3 de produto)**

Ou seja: o documento de produto já distinguia explicitamente entre um motor que **sugere** (F8.1) e um que **executa sozinho** (F8.2) — e já marcava a execução automática como fora do escopo do MVP.

### 2.2 `CAMPAIA_PRODUCT_CHARTER.md` — Tabela de Níveis de Autonomia

> Nível 0 (Assistente, ❌ MVP) · **Nível 1 (Aprovado, ✅ MVP começa aqui)** · Nível 2 (Limitado: "Otimiza dentro de limites predefinidos", ⏳ Fase 2 produto) · Nível 3 (Operacional: "Executa rotinas de baixo risco", ⏳ Fase 3 produto)
> "MVP começa no Nível 1."

### 2.3 `OUT_OF_SCOPE.md` (linha 39)

> "❌ Otimizações automáticas agressivas (>10% mudança)"

**Nota importante sobre nomenclatura:** as "Fases" do Charter (Fase 0 = documentação base, Fase 1 = Foundation+MVP, Fase 2 = Produção controlada, Fase 3 = Autonomia limitada) são fases do **roadmap de produto**, e não devem ser confundidas com as "Fases 0–12" do painel de execução técnica (que descrevem etapas de construção de código, atualmente na Fase técnica 3 = "Núcleo de campanhas + camada HTTP"). São duas numerações independentes.

### 2.4 Por que isso gerou uma pergunta ao Diretor, em vez de uma decisão unilateral

Construir um motor que já executasse mudanças sozinho contrariaria uma decisão de escopo já registrada na Fase 0 (F8.2 fora do MVP). Como esta é uma decisão de escopo com consequência real — e não uma escolha técnica de implementação — a pergunta foi levada ao Diretor antes de qualquer linha de código, com três opções e uma marcada como recomendação. O Diretor respondeu selecionando:

> **"Motor que só sugere/calcula (Recomendado)"**

Confirmando que o motor deve apenas calcular e sugerir otimizações; toda execução de mudança deve continuar passando pelo fluxo de aprovação humana já existente (Nível 1 / `AutonomyLevel.APROVADO`).

---

## 3. Verificação de não-duplicação com o código já existente

Antes de escrever `pacing.py` e `optimizer.py`, os seguintes módulos já existentes em `campaia_core/` foram lidos por completo para confirmar que não havia sobreposição:

- **`autonomy.py`**: já implementa `AutonomyLevel`, `ActionKind`, `AutonomySettings` e a função `evaluate()`, que decide deterministicamente (sem LLM) se uma ação exige aprovação humana. O MVP tem `AutonomySettings().max_level_allowed = AutonomyLevel.APROVADO` — ou seja, **qualquer** `ActionKind` avaliado hoje retorna `requires_human=True`. Este mecanismo pré-existente é o que torna o motor de otimização seguro por construção, sem precisar de nenhuma lógica de autorização nova.
- **`policy.py`**: `PolicyEngine.evaluate()` já consome `evaluate_autonomy()` internamente ao decidir uma `PolicyRequest`. É o caminho de consumo pretendido para qualquer `Recommendation` do B5.
- **`states.py`**: a máquina de estados de campanha já inclui `CampaignState.OPTIMIZING`, alcançável a partir de `ACTIVE` — confirma que a arquitetura já antecipava um motor de otimização, mas os módulos do B5 não fazem transições de estado por conta própria.
- **`budget.py`**: `BudgetEngine` cobre reservas financeiras e limites diários/totais, mas **não** cobre pacing (ritmo de gasto ao longo do tempo) nem otimização por performance — confirmando que o B5 preenche uma lacuna real, sem duplicar nada existente.

---

## 4. Código construído

### 4.1 `campaia_core/pacing.py` (7854 bytes)

Motor de pacing: calcula se o ritmo de gasto de uma campanha está adequado em relação ao período orçamentário.

- `PacingWindow(start_date, end_date, total_amount)` — janela orçamentária, com validação (data final não pode ser anterior à data inicial; orçamento deve ser positivo). Calcula `total_days`, `elapsed_days(as_of)` e `expected_spend(as_of)` (proporção linear do orçamento total).
- `PacingStatus`: `ON_TRACK`, `UNDERPACING`, `OVERPACING`, `EXHAUSTED`.
- `PacingEngine(window, tolerance_pct=15)` — método `assess(actual_spend, as_of)` retorna um `PacingAssessment` imutável com status, variância (valor e percentual), gasto esperado vs. real, `suggested_daily_cap` (quando aplicável) e dias restantes.
- Regras: `EXHAUSTED` se o gasto real já atingiu/ultrapassou o total do período; sem sugestão quando não há dias restantes (período encerrado); `OVERPACING`/`UNDERPACING` quando a variância excede a tolerância configurada, com um teto diário sugerido recalculado como `(total_amount - actual_spend) / remaining_days`; `ON_TRACK` caso contrário.

### 4.2 `campaia_core/optimizer.py` (6927 bytes)

Motor de regras de otimização — implementa F8.1, **não implementa F8.2** (deliberadamente, por confirmação do Diretor).

- `PerformanceSnapshot(ctr, cpc, cpa, volume, currency)` e `OptimizationTargets(cpa_target, volume_target, high_ctr_threshold=0.02, cpa_multiplier_for_pause=2, high_cpc_ceiling=0)`.
- `RecommendationCode`: `INCREASE_BUDGET_HIGH_CTR`, `PAUSE_HIGH_CPA`, `ADJUST_BID_LOW_VOLUME`, `EXPAND_AUDIENCE_HIGH_CPC`.
- `Recommendation(code, action: ActionKind, explanation, suggested_change_pct=None, metrics=None)` — **dataclass frozen**, sem métodos `apply()` ou `execute()`. É dado, não é uma ação executável.
- `evaluate_campaign(campaign_id, snapshot, targets) -> OptimizationReport` aplica as 4 regras de F8.1, cada uma mapeada para um `ActionKind` do `autonomy.py` já existente:
  - CTR acima do limite → `ActionKind.BUDGET_INCREASE`, sugestão padrão de +10%.
  - CPA acima de `cpa_target × cpa_multiplier_for_pause` → `ActionKind.PAUSE`.
  - Volume abaixo da meta → `ActionKind.BID_ADJUSTMENT`, sugestão padrão de +5%.
  - CPC acima de um teto configurado (quando configurado; teto 0 = regra inativa) → `ActionKind.TARGETING_CHANGE`.

Os percentuais padrão (10% para orçamento, 5% para lance) foram escolhidos citando `OUT_OF_SCOPE.md` ("otimizações automáticas agressivas (>10% mudança)" está fora de escopo) como referência de conservadorismo, mesmo sendo apenas sugestões e nunca execuções.

---

## 5. Testes escritos (26 novos, todos reais — sem mocks do mecanismo de autonomia)

### 5.1 `tests/test_pacing.py` (5561 bytes, 14 testes)

Cobre validações de `PacingWindow` (rejeita datas invertidas, rejeita orçamento não positivo, `total_days` inclusivo, `elapsed_days` antes do início é zero, `expected_spend` é linear) e o motor `PacingEngine.assess()`: dentro da tolerância (`ON_TRACK`), overpacing sugere teto diário menor (cenário concreto: janela de 10 dias / R$1000 total, no dia 5 com R$800 já gastos → `remaining_days=5`, sugestão exata `Decimal("40.00")`), underpacing sugere teto diário maior (sugestão exata `Decimal("160.00")`), `EXHAUSTED` quando o total já foi comprometido, sem sugestão quando não há dias restantes (mesmo fora do ritmo), tolerância negativa é rejeitada, e sinal correto de variância (positiva/negativa).

### 5.2 `tests/test_optimizer.py` (7888 bytes, 12 testes)

Testes de gatilho/não-gatilho para cada uma das 4 regras nos limites exatos (ex.: CPA exatamente em 2× o alvo **não** dispara pausa, só acima disso dispara), coexistência de múltiplas regras, e a classe central desta entrega:

> **`TestRecommendationsNeverSelfAuthorize`** — prova, com uma chamada real (não simulada) a `evaluate_autonomy()` do `autonomy.py` já existente, que toda `ActionKind` emitida por qualquer recomendação do motor retorna `requires_human=True` sob o teto de autonomia padrão do MVP (`AutonomySettings()`, teto `AutonomyLevel.APROVADO`). Um segundo teste confirma estruturalmente que `Recommendation` não tem métodos `apply()`/`execute()` e é imutável (`frozen=True` — tentativa de alteração de campo levanta exceção).

Esta é a prova concreta de que a restrição "só sugere, nunca executa" confirmada pelo Diretor está de fato integrada ao mecanismo de aprovação já existente no sistema, e não é apenas uma promessa em comentário de código.

---

## 6. Resultado dos testes (re-execução completa, sem confiar em relatório anterior)

Executado diretamente via Bash nesta sessão, em `/home/claude/backend`:

```
$ python3 -m unittest discover -s tests -p "test_*.py"
Ran 263 tests in 0.037s
OK

$ python3 -m unittest discover -s tests_api -p "test_*.py"
Ran 80 tests in 0.704s
OK
```

**Total: 263 (domínio) + 80 (API/persistência) = 343 testes, 100% aprovados, zero regressão.**

Antes do B5 (linha de base herdada do fechamento do P-19): 237 (domínio) + 80 (API/persistência) = 317. O B5 adicionou 26 testes novos ao domínio (14 pacing + 12 optimizer), levando o domínio de 237 → 263. A suíte de API/persistência permanece inalterada em 80/80, pois o B5 não tocou em `api/`.

---

## 7. Uploads ao Google Drive (verificados por tamanho em bytes)

Todos os 4 arquivos novos foram enviados à pasta de evidências/código do projeto no Drive, cada um com verificação de tamanho local (Python, comparação byte a byte antes do envio) e verificação do tamanho retornado pelo Drive após o envio:

| Arquivo | Pasta Drive | Tamanho local | Tamanho no Drive | Verificação | fileId |
|---|---|---|---|---|---|
| `campaia_core/pacing.py` | `campaia_core/` | 7854 bytes | 7854 | ✅ exato | `1OW34zYLb_tf-dt1CxiNcdC0tOnF9p6fa` |
| `campaia_core/optimizer.py` | `campaia_core/` | 6927 bytes | 6927 | ✅ exato | `1sr4UyeVSASuVntjhnR3ZzE_HuAHEyb41` |
| `tests/test_pacing.py` | `tests/` | 5561 bytes | 5561 | ✅ exato | `1339ErqgiR9h2nErWntL0XDCipcOxF6KM` |
| `tests/test_optimizer.py` | `tests/` | 7888 bytes | 7888 | ✅ exato | `1whc522e-A0nidBXOKruL0W_4oDHHlQnM` |

Nenhum destes arquivos existia anteriormente — são módulos novos, sem substituição de versão anterior (portanto não houve necessidade de trash de arquivo antigo nesta parte do processo).

---

## 8. O que o B5 entrega e o que deliberadamente não entrega

**Entrega (F8.1, confirmado pelo Diretor):**
- Cálculo de ritmo de gasto (pacing) com sugestão de teto diário ajustado quando fora do ritmo.
- Sugestão de aumento de orçamento quando CTR está alto.
- Sugestão de pausa quando CPA está muito acima do alvo.
- Sugestão de ajuste de lance quando o volume está abaixo da meta.
- Sugestão de expansão de público quando o CPC está acima de um teto configurado.
- Toda sugestão é dado imutável, nunca uma ação executável, e toda `ActionKind` emitida passa pelo mecanismo de autonomia já existente, que hoje sempre exige aprovação humana.

**Não entrega, por decisão explícita do Diretor (F8.2 permanece fora de escopo):**
- Nenhuma execução automática de qualquer mudança (orçamento, lance, pausa, público) — mesmo para ajustes pequenos.
- Nenhum novo mecanismo de autorização — o motor reutiliza o `autonomy.py`/`policy.py` já existentes, propositalmente, para não criar um caminho paralelo de decisão.

---

## 9. Resumo executivo

| Item | Valor |
|---|---|
| Autorização do Diretor | "siga sua recomendação" (bloco) + "Motor que só sugere/calcula" (escopo) |
| Módulos novos | `pacing.py` (7854 B), `optimizer.py` (6927 B) |
| Testes novos | 26 (14 pacing + 12 optimizer) |
| Testes totais pós-B5 | 343 (263 domínio + 80 API/persistência), 100% aprovados |
| Regressão | Zero |
| Uploads Drive | 4/4, todos byte-verificados |
| F8.2 (execução automática) | Fora de escopo, confirmado pelo Diretor — não implementado |

---

*Documento gerado e verificado nesta sessão via re-execução direta dos testes e verificação byte a byte de cada upload ao Drive, seguindo a disciplina de evidência do projeto CAMPAIA.*
