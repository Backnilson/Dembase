"""
=============================================================================
DemBase v3 — test_ux_novo_lancamento.py (Flet 1.0.1)
Bateria de Testes E2E da Reformulação de UX/UI do Modal "Novo Lançamento":
1. Nova ordem no topo (Tipo -> Descrição + Auto-Complete + Ranking Vivo -> Valor -> Data/Hora/Status)
2. Fluxo Obrigatório: Digitar "Café" -> Auto-preenchimento de Perfil, Pix, Conta,
   Categoria, Subcategoria e Pote Financeiro a partir do histórico -> Digitar Valor -> Salvar.
3. Atalhos Rápidos (1 toque preenche descrição + histórico e foca no campo Valor).
4. Seleção em 1 Clique com feedback visual imediato:
   - Perfil Familiar ([👤 Denilson] [👤 Erika])
   - Forma de Movimentação ([Pix] [Crédito] [Débito] [Caixinha]) com filtro dinâmico abaixo
   - Pote Financeiro (6 Potes coloridos em pílulas de 1 clique)
5. Auto-Complete Instantâneo a partir de 3 Letras + Memória Evolutiva ("Última Configuração Salva"):
   - Digitar "caf" ou "gas" exibe a sugestão sem travar a digitação e preenche o formulário;
   - Alterar de Pix + Santander para Crédito + Inter e salvar evolui automaticamente a memória!
6. Ranking Vivo de Atalhos Rápidos separado por Aba (Despesa | Receita | Transf.):
   - Começa limpo (sem itens estáticos), ignora recorrências automáticas (Google One, Garagem Moto,
     parcelas Caixa de Som (DJ)), ordena por frequência (Moto 3x em 1º, Café 1x em 2º) e alterna
     instantaneamente ao trocar entre Despesa, Receita e Transferência.
=============================================================================
"""
import sys
import os
from unittest.mock import MagicMock, patch
import flet as ft

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(__file__))

import services.supabase_client as db
from core.lancamento_state import LancamentoFormState
from views.widgets.lancamento_form import LancamentoForm
from views.widgets.lancamento_sheet import abrir_lancamento


def criar_mock_page(width=1280, height=800):
    page = MagicMock(spec=ft.Page)
    page.width = width
    page.height = height
    page.route = "/dashboard"
    page.views = []
    page.overlay = []
    page.session = {}
    page._session_store = {}
    page.client_storage = MagicMock()
    page.update = MagicMock()
    page.show_dialog = MagicMock()
    page.pop_dialog = MagicMock()
    page.run_task = MagicMock()
    return page


# Dados simulados realistas da família
MEMBROS_MOCK = [
    {"id": "mem-denilson", "nome": "Denilson", "cor": "#00E676", "principal": True},
    {"id": "mem-erika",    "nome": "Erika",    "cor": "#EC4899", "principal": False},
]

CONTAS_MOCK = [
    {"id": "cnt-santander", "nome": "Santander", "membro_id": "mem-denilson"},
    {"id": "cnt-inter",     "nome": "Inter",     "membro_id": "mem-denilson"},
    {"id": "cnt-nubank-e",  "nome": "Nubank Erika", "membro_id": "mem-erika"},
]

CARTOES_MOCK = [
    {"id": "crd-santander", "nome": "Santander Unique", "membro_id": "mem-denilson"},
    {"id": "crd-inter",     "nome": "Inter Black",      "membro_id": "mem-denilson"},
    {"id": "crd-nubank-e",  "nome": "Nubank Ultravioleta", "membro_id": "mem-erika"},
]

CATEGORIAS_MOCK = [
    {"id": "cat-alim",   "nome": "Alimentação"},
    {"id": "cat-transp", "nome": "Transporte"},
    {"id": "cat-lazer",  "nome": "Lazer"},
    {"id": "cat-renda",  "nome": "Renda"},
]

SUBCATEGORIAS_MOCK = [
    {"id": "sub-cafe",     "categoria_id": "cat-alim",   "nome": "Café"},
    {"id": "sub-almoco",   "categoria_id": "cat-alim",   "nome": "Almoço"},
    {"id": "sub-mercado",  "categoria_id": "cat-alim",   "nome": "Mercado"},
    {"id": "sub-gasolina", "categoria_id": "cat-transp", "nome": "Gasolina"},
    {"id": "sub-moto",     "categoria_id": "cat-transp", "nome": "Moto"},
    {"id": "sub-bebida",   "categoria_id": "cat-lazer",  "nome": "Bebida"},
    {"id": "sub-salario",  "categoria_id": "cat-renda",  "nome": "Salário"},
]

CAIXINHAS_MOCK = [
    {
        "id": "cx-viagem",
        "nome": "Caixinha Fim de Semana",
        "saldo_atual": 450.0,
        "pote_id": "c82b0736-fb01-419f-8155-923ebfec82b2",
        "categoria_id": "cat-lazer",
        "subcategoria_id": "sub-bebida",
    }
]

POTES_MOCK = [
    {"id": "2df4dd2f-4353-42cc-a5c9-8983085a5301", "posicao": 1, "nome": "Custos Fixos",         "percentual": 30.0, "cor": "#007AFF"},
    {"id": "da6e1d2b-c611-481d-b48d-065cc5d584b4", "posicao": 2, "nome": "Custos Semi Fixos",    "percentual": 20.0, "cor": "#FF69B4"},
    {"id": "986da9e8-3042-4562-b1df-c1f5cf0138b9", "posicao": 3, "nome": "Metas",                "percentual": 15.0, "cor": "#800080"},
    {"id": "c82b0736-fb01-419f-8155-923ebfec82b2", "posicao": 4, "nome": "Prazeres",             "percentual": 10.0, "cor": "#FF7A00"},
    {"id": "1f1f7449-d985-4c2a-b807-0570a5526614", "posicao": 5, "nome": "Conhecimento",         "percentual": 5.0,  "cor": "#FFD60A"},
    {"id": "34a47be1-9879-46bd-96b1-4082703bf388", "posicao": 6, "nome": "Liberdade Financeira", "percentual": 20.0, "cor": "#6C5CE7"},
]

HISTORICO_MEMORIA_MOCK = [
    {
        "id": "lanc-hist-cafe",
        "descricao": "Café",
        "tipo": "Despesa",
        "subtipo": "Despesa",
        "forma_movimentacao": "Pix",
        "conta_id": "cnt-santander",
        "cartao_id": None,
        "caixinha_id": None,
        "categoria_id": "cat-alim",
        "subcategoria_id": "sub-cafe",
        "pote_id": "c82b0736-fb01-419f-8155-923ebfec82b2",
        "regra": "Estilo de Vida",
        "membro_id": "mem-denilson",
        "valor": 14.0,
        "data": "2026-11-04",
        "hora": 9,
        "tipo_recorrencia": "unica",
    },
    {
        "id": "lanc-hist-gasolina",
        "descricao": "Gasolina",
        "tipo": "Despesa",
        "subtipo": "Despesa",
        "forma_movimentacao": "Crédito",
        "conta_id": None,
        "cartao_id": "crd-nubank-e",
        "caixinha_id": None,
        "categoria_id": "cat-transp",
        "subcategoria_id": "sub-gasolina",
        "pote_id": "da6e1d2b-c611-481d-b48d-065cc5d584b4",
        "regra": "Essencial",
        "membro_id": "mem-erika",
        "valor": 220.0,
        "data": "2026-11-03",
        "hora": 18,
        "tipo_recorrencia": "unica",
    },
]


def _patches_padrao(historico=None):
    hist_alvo = HISTORICO_MEMORIA_MOCK if historico is None else historico
    return (
        patch("services.supabase_client.listar_membros", return_value=MEMBROS_MOCK),
        patch("services.supabase_client.listar_contas", return_value=CONTAS_MOCK),
        patch("services.supabase_client.listar_cartoes", return_value=CARTOES_MOCK),
        patch("services.supabase_client.listar_categorias", return_value=CATEGORIAS_MOCK),
        patch("services.supabase_client.listar_subcategorias", side_effect=lambda cid=None: (
            [s for s in SUBCATEGORIAS_MOCK if str(s["categoria_id"]) == str(cid)]
            if cid else SUBCATEGORIAS_MOCK
        )),
        patch("services.supabase_client.listar_caixinhas_opcoes", return_value=CAIXINHAS_MOCK),
        patch("services.supabase_client.obter_memoria_lancamentos", side_effect=lambda *a, **kw: db._mesclar_e_ordenar_memoria(hist_alvo)),
        patch("services.potes_service.carregar_potes", return_value=POTES_MOCK),
    )


def test_1_ordem_topo_e_ausencia_acordeao():
    print("--- 1. Testando Nova Ordem no Topo, Grid Lado a Lado e Fim do 'Mais Detalhes' ---")
    db.limpar_memoria_evolutiva_lancamentos()
    page = criar_mock_page()
    state = LancamentoFormState()

    p1, p2, p3, p4, p5, p6, p7, p8 = _patches_padrao()
    with p1, p2, p3, p4, p5, p6, p7, p8:
        form = LancamentoForm(page, state)

        # Verifica ordem dos primeiros controles do formulário
        assert form.controls[0] is form.btn_tipo, "1º controle deve ser o seletor Despesa | Receita | Transf."
        assert form.controls[1] is form.sec_descricao_topo, "2º controle (no topo) deve ser a seção de Descrição + Atalhos Rápidos"
        assert form.controls[2] is form.txt_valor, "3º controle deve ser o Valor da transação"
        assert form.controls[3] is form.sec_data_hora_status, "4º controle deve ser a barra unificada Data + Hora + Status"

        # Verifica eliminação do botão 'Mais detalhes / Menos detalhes' e do campo 'Subtipo' na UI
        assert not hasattr(form, "btn_toggle_detalhes"), "Botão 'Mais detalhes' deve ter sido eliminado"
        assert form.dd_subtipo not in form.controls, "Campo Subtipo não deve estar visível na interface"
        assert form.row_cat_subcat_grid.visible is True, "Grid Categoria + Subcategoria deve estar sempre visível"
        assert form.sec_potes.visible is True, "Pílulas dos 6 Potes devem estar sempre visíveis em Despesas"
        assert len(form.wrap_chips_potes.controls) == 6, "Devem ser renderizadas exatamente 6 pílulas de Potes"

    print("  [OK] Layout em tela única escaneável validado com sucesso.")


def test_2_fluxo_obrigatorio_digitar_cafe_e_salvar():
    print("--- 2. Testando Checklist Obrigatório: Digitar 'Café' -> Auto-Fill Completo -> Valor -> Salvar ---")
    db.limpar_memoria_evolutiva_lancamentos()
    page = criar_mock_page()

    p1, p2, p3, p4, p5, p6, p7, p8 = _patches_padrao()
    with p1, p2, p3, p4, p5, p6, p7, p8, \
         patch("services.supabase_client.criar_lancamento_recorrente", return_value={"sucesso": True, "id": "novo-cafe-1"}) as mock_salvar:

        # Abre o modal começando com outros valores para provar que o Auto-Fill preenche tudo sozinho
        abrir_lancamento(
            page=page,
            conta_inicial="cnt-nubank-e",
            categoria_inicial="cat-transp",
            pote_inicial="2df4dd2f-4353-42cc-a5c9-8983085a5301",
        )
        dialog = page.show_dialog.call_args[0][0]
        form: LancamentoForm = dialog.content.content

        # 1. Usuário digita "Café" no campo de Descrição
        ev_desc = MagicMock()
        ev_desc.control.value = "Café"
        form._ao_mudar_descricao(ev_desc)

        # 2. Verifica se Perfil, Pix, Conta, Categoria, Subcategoria e Pote foram preenchidos sozinhos!
        assert form.state.tipo == "Despesa"
        assert form.state.membro_id == "mem-denilson", f"Perfil deveria ser mem-denilson, obtido: {form.state.membro_id}"
        assert form.state.forma_movimentacao == "Pix", f"Forma deveria ser Pix, obtido: {form.state.forma_movimentacao}"
        assert form.state.conta_id == "cnt-santander", f"Conta deveria ser cnt-santander, obtido: {form.state.conta_id}"
        assert form.state.categoria_id == "cat-alim", f"Categoria deveria ser cat-alim, obtido: {form.state.categoria_id}"
        assert form.state.subcategoria_id == "sub-cafe", f"Subcategoria deveria ser sub-cafe, obtido: {form.state.subcategoria_id}"
        assert form.state.pote_id == "c82b0736-fb01-419f-8155-923ebfec82b2", "Pote deveria ser Prazeres"
        assert form.state.regra == "Estilo de Vida"
        assert form.badge_autofill.visible is True, "Badge visual de Auto-preenchimento deve estar visível"

        # 3. Usuário digita apenas o Valor (ex: R$ 15,90 -> "1590")
        ev_val = MagicMock()
        ev_val.control.value = "1590"
        form._ao_mudar_valor(ev_val)
        assert form.state.valor == 15.90
        assert form.txt_valor.value == "15,90"

        # 4. Usuário clica em Confirmar Lançamento (Salvar)
        btn_salvar = next(a for a in dialog.actions if isinstance(a, ft.FilledButton))
        btn_salvar.on_click(MagicMock())

        assert mock_salvar.called, "db.criar_lancamento_recorrente deve ter sido chamado"
        dados_gravados = mock_salvar.call_args[1]["dados"]
        assert dados_gravados["descricao"] == "Café"
        assert dados_gravados["valor"] == 15.90
        assert dados_gravados["membro_id"] == "mem-denilson"
        assert dados_gravados["forma_movimentacao"] == "Pix"
        assert dados_gravados["conta_id"] == "cnt-santander"
        assert dados_gravados["categoria_id"] == "cat-alim"
        assert dados_gravados["subcategoria_id"] == "sub-cafe"
        assert dados_gravados["pote_id"] == "c82b0736-fb01-419f-8155-923ebfec82b2"
        assert dados_gravados["regra"] == "Estilo de Vida"
        assert dados_gravados["subtipo"] == "Despesa"

    print("  [OK] Fluxo Ponta a Ponta 'Café' -> Auto-Fill -> Valor -> Salvar 100% aprovado!")


def test_3_atalhos_rapidos_e_chips_1_clique():
    print("--- 3. Testando Atalhos Rápidos (1 toque) e Chips de 1 Clique (Perfil, Forma e 6 Potes) ---")
    db.limpar_memoria_evolutiva_lancamentos()
    page = criar_mock_page()
    state = LancamentoFormState()

    p1, p2, p3, p4, p5, p6, p7, p8 = _patches_padrao()
    with p1, p2, p3, p4, p5, p6, p7, p8:
        form = LancamentoForm(page, state)

        # 1. Clicar no chip de Atalho Rápido "Gasolina"
        atalhos = form._obter_lista_atalhos_rapidos()
        atalho_gas = next(a for a in atalhos if a["chave"] == "gasolina")
        form._aplicar_atalho_rapido(atalho_gas)

        assert form.txt_descricao.value == "Gasolina"
        assert form.state.membro_id == "mem-erika"
        assert form.state.forma_movimentacao == "Crédito"
        assert form.state.cartao_id == "crd-nubank-e"
        assert form.state.categoria_id == "cat-transp"
        assert form.state.subcategoria_id == "sub-gasolina"
        assert form.state.pote_id == "da6e1d2b-c611-481d-b48d-065cc5d584b4"

        # 2. Clicar no chip de Forma de Movimentação [Caixinha] (1 clique)
        form._selecionar_forma_chip("Caixinha")
        assert form.state.eh_caixinha is True
        assert form.row_caixinha.visible is True, "Seletor de Caixinha deve aparecer abaixo de Forma"
        assert form.row_conta.visible is False, "Seletor de Conta/Cartão deve ocultar quando Caixinha está ativa"
        assert form.row_parcelas.visible is False
        assert form.state.caixinha_id == "cx-viagem"

        # 3. Clicar no chip de Forma de Movimentação [Débito] (1 clique)
        form._selecionar_forma_chip("Débito")
        assert form.state.eh_caixinha is False
        assert form.state.eh_credito is False
        assert form.row_conta.visible is True, "Seletor de Conta deve aparecer quando Débito está ativo"
        assert form.row_caixinha.visible is False

        # 4. Clicar no chip de Perfil Familiar [Denilson] (1 clique)
        form._selecionar_membro_chip("mem-denilson")
        assert form.state.membro_id == "mem-denilson"
        assert form.state.conta_id == "cnt-santander", "Deve sugerir automaticamente a conta do membro selecionado"

        # 5. Clicar na pílula do Pote 5 (Conhecimento) em 1 clique
        form._selecionar_pote_chip("1f1f7449-d985-4c2a-b807-0570a5526614")
        assert form.state.pote_id == "1f1f7449-d985-4c2a-b807-0570a5526614"
        assert form.state.regra == "Investimento"

    print("  [OK] Atalhos Rápidos e Chips de 1 Clique validados com feedback imediato.")


def test_4_responsividade_desktop_e_mobile():
    print("--- 4. Testando Responsividade do Modal no Desktop e no Mobile ---")
    db.limpar_memoria_evolutiva_lancamentos()
    p1, p2, p3, p4, p5, p6, p7, p8 = _patches_padrao()
    with p1, p2, p3, p4, p5, p6, p7, p8:
        # Desktop (1280x800) -> AlertDialog
        page_desk = criar_mock_page(width=1280, height=800)
        abrir_lancamento(page_desk)
        dlg_desk = page_desk.show_dialog.call_args[0][0]
        assert isinstance(dlg_desk, ft.AlertDialog), "No Desktop deve abrir ft.AlertDialog"

        # Mobile (390x844) -> BottomSheet scrollable=True
        page_mob = criar_mock_page(width=390, height=844)
        abrir_lancamento(page_mob)
        dlg_mob = page_mob.show_dialog.call_args[0][0]
        assert isinstance(dlg_mob, ft.BottomSheet), "No Mobile deve abrir ft.BottomSheet"
        assert dlg_mob.scrollable is True, "BottomSheet no Mobile deve ter scrollable=True"

    print("  [OK] Modal Desktop (AlertDialog) e Mobile (BottomSheet) validados com sucesso.")


def test_5_autocomplete_3_letras_e_memoria_evolutiva():
    print("--- 5. Testando Auto-Complete nas 3 Primeiras Letras + Memória Evolutiva ('Última Configuração Salva') ---")
    db.limpar_memoria_evolutiva_lancamentos()
    page = criar_mock_page()

    p1, p2, p3, p4, p5, p6, p7, p8 = _patches_padrao()
    with p1, p2, p3, p4, p5, p6, p7, p8, \
         patch("services.supabase_client.criar_lancamento_recorrente", return_value={"sucesso": True, "id": "lanc-cafe-evoluido"}):

        # Passo A: Abre o modal pela 1ª vez
        abrir_lancamento(page=page)
        dialog1 = page.show_dialog.call_args[0][0]
        form1: LancamentoForm = dialog1.content.content

        # Digita apenas 2 letras ("ca") -> NÃO deve ativar o auto-complete ainda
        ev_2letras = MagicMock()
        ev_2letras.control.value = "ca"
        form1._ao_mudar_descricao(ev_2letras)
        assert form1.box_autocomplete.visible is False, "Com menos de 3 letras não deve exibir auto-complete"

        # Digita 3 letras ("caf") -> Deve exibir imediatamente a sugestão de Auto-Complete sem travar o texto ("caf")
        ev_3letras = MagicMock()
        ev_3letras.control.value = "caf"
        form1._ao_mudar_descricao(ev_3letras)
        assert form1.txt_descricao.value == "caf", "Não deve sobrescrever o texto enquanto o usuário digita"
        assert form1.box_autocomplete.visible is True, "Com 3 letras ('caf') o box de auto-complete deve aparecer imediatamente"
        assert len(form1.sugestoes_atuais) >= 1 and form1.sugestoes_atuais[0]["label"] == "Café"

        # E já deve ter pré-preenchido com a configuração anterior de Café (Pix + Santander + Denilson + Alimentação > Café + Prazeres)
        assert form1.state.membro_id == "mem-denilson"
        assert form1.state.forma_movimentacao == "Pix"
        assert form1.state.conta_id == "cnt-santander"
        assert form1.state.categoria_id == "cat-alim"
        assert form1.state.subcategoria_id == "sub-cafe"
        assert form1.state.pote_id == "c82b0736-fb01-419f-8155-923ebfec82b2"

        # Seleciona/confirma a sugestão do auto-complete -> completa "Café" e fecha o box
        form1._selecionar_sugestao_autocomplete(form1.sugestoes_atuais[0])
        assert form1.txt_descricao.value == "Café"
        assert form1.box_autocomplete.visible is False

        # Passo B (EVOLUÇÃO AUTOMÁTICA): Usuário muda manualmente para Crédito + Cartão Inter Black e salva!
        form1._selecionar_forma_chip("Crédito")
        ev_cartao = MagicMock()
        ev_cartao.data = "crd-inter"
        ev_cartao.control.value = "crd-inter"
        form1._ao_mudar_conta(ev_cartao)
        assert form1.state.forma_movimentacao == "Crédito"
        assert form1.state.cartao_id == "crd-inter"

        ev_val = MagicMock()
        ev_val.control.value = "1850"
        form1._ao_mudar_valor(ev_val)

        btn_salvar1 = next(a for a in dialog1.actions if isinstance(a, ft.FilledButton))
        btn_salvar1.on_click(MagicMock())

        # Passo C: Abre o modal novamente e digita 3 letras ("caf") -> Deve puxar a NOVA configuração (Crédito + Inter Black)!
        page._dembase_lanc_ts = 0.0  # libera guard de 1.5s para o teste
        abrir_lancamento(page=page)
        dialog2 = page.show_dialog.call_args[0][0]
        form2: LancamentoForm = dialog2.content.content

        ev_caf_novo = MagicMock()
        ev_caf_novo.control.value = "caf"
        form2._ao_mudar_descricao(ev_caf_novo)

        assert form2.box_autocomplete.visible is True
        assert form2.state.forma_movimentacao == "Crédito", f"Memória evolutiva deveria puxar 'Crédito', mas puxou '{form2.state.forma_movimentacao}'"
        assert form2.state.cartao_id == "crd-inter", f"Memória evolutiva deveria puxar 'crd-inter', mas puxou '{form2.state.cartao_id}'"
        assert form2.state.conta_id is None
        assert form2.state.categoria_id == "cat-alim"
        assert form2.state.subcategoria_id == "sub-cafe"
        assert form2.state.pote_id == "c82b0736-fb01-419f-8155-923ebfec82b2"

        # Testa também digitar 3 letras "gas" para Gasolina
        ev_gas = MagicMock()
        ev_gas.control.value = "gas"
        form2._ao_mudar_descricao(ev_gas)
        assert form2.box_autocomplete.visible is True
        assert form2.sugestoes_atuais[0]["label"] == "Gasolina"
        assert form2.state.membro_id == "mem-erika"
        assert form2.state.forma_movimentacao == "Crédito"
        assert form2.state.cartao_id == "crd-nubank-e"
        assert form2.state.categoria_id == "cat-transp"
        assert form2.state.subcategoria_id == "sub-gasolina"

    print("  [OK] Auto-Complete em 3 letras ('caf'/'gas') + Memória Evolutiva ('Crédito + Inter') 100% aprovados!")


def test_6_ranking_vivo_frequencia_separado_por_aba():
    print("--- 6. Testando Ranking Vivo por Frequência (Moto 3x > Café 1x), Ignorando Recorrências e Separado por Aba ---")
    db.limpar_memoria_evolutiva_lancamentos()
    page = criar_mock_page()

    # 1. Histórico completamente vazio -> O ranking deve começar limpo (0 pílulas estáticas!)
    p1, p2, p3, p4, p5, p6, p7, p8 = _patches_padrao(historico=[])
    with p1, p2, p3, p4, p5, p6, p7, p8:
        form_limpo = LancamentoForm(page, LancamentoFormState())
        assert len(form_limpo.row_atalhos_rapidos.controls) == 0, "O ranking deve começar limpo sem itens estáticos"

    # 2. Histórico contendo:
    # - Recorrências automáticas e parcelas (Google One 12x, Garagem Moto fixa, Caixa de Som (DJ) (2/10)) -> DEVEM SER IGNORADAS!
    # - Despesas manuais: "Moto" (3 vezes) e "Café" (1 vez) -> Moto em 1º lugar (3x) e Café em 2º lugar (1x)!
    # - Receitas manuais: "Salário" (2 vezes) e "Freela DJ" (1 vez) -> Salário em 1º e Freela DJ em 2º na aba Receita!
    # - Transferências manuais: "Reserva Inter" (2 vezes) -> Reserva Inter em 1º na aba Transf.!
    historico_misto = [
        # Recorrências automáticas e parcelas que poluíam o modal antes:
        {"id": "rec-1", "descricao": "Google One", "tipo": "Despesa", "recorrente_id": "r-google", "tipo_recorrencia": "fixa", "data": "2027-03-01"},
        {"id": "rec-2", "descricao": "Google One", "tipo": "Despesa", "recorrente_id": "r-google", "tipo_recorrencia": "fixa", "data": "2027-02-01"},
        {"id": "rec-3", "descricao": "Garagem Moto", "tipo": "Despesa", "tipo_recorrencia": "fixa", "data": "2027-01-10"},
        {"id": "parc-1", "descricao": "Caixa de Som (DJ) (2/10)", "tipo": "Despesa", "serie_id": "s-dj", "parcela_atual": 2, "total_parcelas": 10, "data": "2026-12-10"},
        # Despesas manuais reais: Café (1x) e Moto (3x)
        {"id": "d-cafe-1", "descricao": "Café", "tipo": "Despesa", "forma_movimentacao": "Pix", "conta_id": "cnt-santander", "categoria_id": "cat-alim", "subcategoria_id": "sub-cafe", "pote_id": "c82b0736-fb01-419f-8155-923ebfec82b2", "membro_id": "mem-denilson", "tipo_recorrencia": "unica", "data": "2026-11-05"},
        {"id": "d-moto-1", "descricao": "Moto", "tipo": "Despesa", "forma_movimentacao": "Pix", "conta_id": "cnt-inter", "categoria_id": "cat-transp", "subcategoria_id": "sub-moto", "pote_id": "da6e1d2b-c611-481d-b48d-065cc5d584b4", "membro_id": "mem-denilson", "tipo_recorrencia": "unica", "data": "2026-11-04"},
        {"id": "d-moto-2", "descricao": "Moto", "tipo": "Despesa", "forma_movimentacao": "Pix", "conta_id": "cnt-santander", "categoria_id": "cat-transp", "subcategoria_id": "sub-moto", "pote_id": "da6e1d2b-c611-481d-b48d-065cc5d584b4", "membro_id": "mem-denilson", "tipo_recorrencia": "unica", "data": "2026-11-02"},
        {"id": "d-moto-3", "descricao": "Moto", "tipo": "Despesa", "forma_movimentacao": "Pix", "conta_id": "cnt-santander", "categoria_id": "cat-transp", "subcategoria_id": "sub-moto", "pote_id": "da6e1d2b-c611-481d-b48d-065cc5d584b4", "membro_id": "mem-denilson", "tipo_recorrencia": "unica", "data": "2026-11-01"},
        # Receitas manuais reais: Salário (2x) e Freela DJ (1x)
        {"id": "r-sal-1", "descricao": "Salário", "tipo": "Receita", "forma_movimentacao": "Pix", "conta_id": "cnt-santander", "categoria_id": "cat-renda", "subcategoria_id": "sub-salario", "membro_id": "mem-denilson", "tipo_recorrencia": "unica", "data": "2026-11-05"},
        {"id": "r-sal-2", "descricao": "Salário", "tipo": "Receita", "forma_movimentacao": "Pix", "conta_id": "cnt-santander", "categoria_id": "cat-renda", "subcategoria_id": "sub-salario", "membro_id": "mem-denilson", "tipo_recorrencia": "unica", "data": "2026-10-05"},
        {"id": "r-free-1", "descricao": "Freela DJ", "tipo": "Receita", "forma_movimentacao": "Pix", "conta_id": "cnt-inter", "categoria_id": "cat-renda", "membro_id": "mem-denilson", "tipo_recorrencia": "unica", "data": "2026-11-03"},
        # Transferências manuais reais: Reserva Inter (2x)
        {"id": "t-res-1", "descricao": "Reserva Inter", "tipo": "Transferência", "forma_movimentacao": "Pix", "conta_id": "cnt-santander", "destino_id": "cnt-inter", "membro_id": "mem-denilson", "tipo_recorrencia": "unica", "data": "2026-11-04"},
        {"id": "t-res-2", "descricao": "Reserva Inter", "tipo": "Transferência", "forma_movimentacao": "Pix", "conta_id": "cnt-santander", "destino_id": "cnt-inter", "membro_id": "mem-denilson", "tipo_recorrencia": "unica", "data": "2026-10-20"},
    ]

    p1, p2, p3, p4, p5, p6, p7, p8 = _patches_padrao(historico=historico_misto)
    with p1, p2, p3, p4, p5, p6, p7, p8:
        form = LancamentoForm(page, LancamentoFormState())

        # A. Aba DESPESA marcada -> Deve mostrar apenas Despesas manuais, com Moto (3x) em 1º e Café (1x) em 2º!
        ranking_desp = form._obter_lista_atalhos_rapidos()
        labels_desp = [it["label"] for it in ranking_desp]
        assert labels_desp == ["Moto", "Café"], f"Ranking de Despesa deveria ser ['Moto', 'Café'], obtido: {labels_desp}"
        assert ranking_desp[0]["frequencia"] == 3
        assert ranking_desp[1]["frequencia"] == 1
        assert "Google One" not in labels_desp
        assert "Garagem Moto" not in labels_desp
        assert "Caixa de Som (DJ)" not in labels_desp

        # Ao clicar na pílula "Moto", deve puxar a ÚLTIMA configuração salva de Moto (d-moto-1 -> cnt-inter)
        form._aplicar_atalho_rapido(ranking_desp[0])
        assert form.txt_descricao.value == "Moto"
        assert form.state.conta_id == "cnt-inter", "Deve aplicar a última configuração salva para Moto (cnt-inter)"
        assert form.state.subcategoria_id == "sub-moto"

        # B. Alternar para a aba RECEITA -> Pílulas atualizam na hora mostrando apenas Receitas (Salário 2x em 1º, Freela DJ 1x em 2º)
        ev_rec = MagicMock()
        ev_rec.control.selected = ["Receita"]
        form._ao_mudar_tipo(ev_rec)

        ranking_rec = form._obter_lista_atalhos_rapidos()
        labels_rec = [it["label"] for it in ranking_rec]
        assert labels_rec == ["Salário", "Freela DJ"], f"Ranking de Receita deveria ser ['Salário', 'Freela DJ'], obtido: {labels_rec}"
        assert len(form.row_atalhos_rapidos.controls) == 2

        # C. Alternar para a aba TRANSF. -> Pílulas atualizam na hora mostrando apenas Transferências (Reserva Inter 2x)
        ev_tr = MagicMock()
        ev_tr.control.selected = ["Transferencia"]
        form._ao_mudar_tipo(ev_tr)

        ranking_tr = form._obter_lista_atalhos_rapidos()
        labels_tr = [it["label"] for it in ranking_tr]
        assert labels_tr == ["Reserva Inter"], f"Ranking de Transferência deveria ser ['Reserva Inter'], obtido: {labels_tr}"
        assert len(form.row_atalhos_rapidos.controls) == 1

        # Clica na pílula "Reserva Inter" -> Deve preencher origem (cnt-santander) e destino (cnt-inter)
        form._aplicar_atalho_rapido(ranking_tr[0])
        assert form.txt_descricao.value == "Reserva Inter"
        assert form.state.conta_id == "cnt-santander"
        assert form.state.destino_id == "cnt-inter"

    print("  [OK] Ranking Vivo por Frequência separado por Aba (Despesa | Receita | Transf.) 100% aprovado!")


if __name__ == "__main__":
    test_1_ordem_topo_e_ausencia_acordeao()
    test_2_fluxo_obrigatorio_digitar_cafe_e_salvar()
    test_3_atalhos_rapidos_e_chips_1_clique()
    test_4_responsividade_desktop_e_mobile()
    test_5_autocomplete_3_letras_e_memoria_evolutiva()
    test_6_ranking_vivo_frequencia_separado_por_aba()
    print("\n" + "=" * 70)
    print("TODOS OS 6 TESTES E2E DE UX/UI E MEMÓRIA EVOLUTIVA PASSARAM COM 100%!")
    print("=" * 70)
