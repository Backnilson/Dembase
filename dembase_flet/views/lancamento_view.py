"""
=============================================================================
DemBase v3 — views/lancamento_view.py  (Flet 1.0.1 compatible)
Cadastro de lançamentos financeiros com reatividade estrita, cálculo dinâmico
de parcelas no crédito, suporte a Transferência e criação inline de
subtipos, categorias e subcategorias.
=============================================================================
"""
import uuid
import unicodedata
from datetime import datetime
from dateutil.relativedelta import relativedelta
import flet as ft

from core import theme as T
from core.theme import pad, borda, mostrar_feedback
from core.constants import (
    TIPOS_LANCAMENTO, SUBTIPOS_RECEITA, SUBTIPOS_DESPESA, SUBTIPOS_TRANSFERENCIA,
    FORMAS_RECEITA, FORMAS_DESPESA, FORMAS_TRANSFERENCIA,
    STATUS_OPCOES, REGRAS_5030,
    session_get, session_set, session_remove,
)
from core.router import ROTA_DASHBOARD, ROTA_RELATORIOS, navegar
import services.supabase_client as db


def _norm(s: str) -> str:
    """Normaliza strings removendo acentos para comparações 100% seguras."""
    if not s:
        return ""
    return unicodedata.normalize('NFKD', str(s)).encode('ASCII', 'ignore').decode('utf-8').lower()


def criar_view_lancamento(page: ft.Page) -> ft.View:
    # Detecta se é modo de edição via page.session
    edit_id = session_get(page, "edit_lancamento_id")
    lanc_edit = session_get(page, "edit_lancamento_dados")
    if edit_id and not lanc_edit:
        try:
            lanc_edit = db.obter_lancamento(edit_id)
        except Exception:
            lanc_edit = None
    is_edicao = bool(edit_id and lanc_edit)

    contas = db.listar_contas()
    cartoes = db.listar_cartoes()
    categorias_lista = db.listar_categorias()

    def _opts(lst):
        return [ft.dropdown.Option(key=str(i["id"]), text=i["nome"]) for i in lst]

    def _is_uuid(val):
        if not val:
            return False
        try:
            uuid.UUID(str(val).strip())
            return True
        except (ValueError, AttributeError, TypeError):
            return False

    def _obter_cat_id(valor_ou_nome):
        if not valor_ou_nome:
            return None
        v_str = str(valor_ou_nome).strip()
        v_norm = _norm(v_str)
        # 1. Match direto por key
        for opt in dd_categoria.options:
            if opt.key and opt.key == v_str:
                return opt.key
        # 2. Match por text normalizado
        for opt in dd_categoria.options:
            if opt.text and _norm(opt.text) == v_norm:
                return opt.key
        # 3. Match na lista em memória
        for c in categorias_lista:
            if str(c.get("id")) == v_str:
                return str(c["id"])
            if _norm(c.get("nome") or "") == v_norm:
                return str(c["id"])
        if _is_uuid(v_str):
            return v_str
        return None

    def _obter_subcat_id(valor_ou_nome, subs_lista=None):
        if not valor_ou_nome:
            return None
        v_str = str(valor_ou_nome).strip()
        v_norm = _norm(v_str)
        for opt in dd_subcategoria.options:
            if opt.key and opt.key == v_str:
                return opt.key
            if opt.text and _norm(opt.text) == v_norm:
                return opt.key
        if subs_lista:
            for s in subs_lista:
                if str(s.get("id")) == v_str:
                    return str(s["id"])
                if _norm(s.get("nome") or "") == v_norm:
                    return str(s["id"])
        if _is_uuid(v_str):
            return v_str
        return None

    def _obter_conta_id(valor_ou_nome, lista=None):
        if not valor_ou_nome:
            return None
        v_str = str(valor_ou_nome).strip()
        v_norm = _norm(v_str)
        forma_n = _norm(dd_forma.value)
        tipo_n = _norm(dd_tipo.value)
        is_c = ("cred" in forma_n) and ("desp" in tipo_n)
        itens = lista if lista is not None else (cartoes if is_c else contas)
        for item in itens:
            if str(item.get("id")) == v_str:
                return str(item["id"])
            if _norm(item.get("nome") or "") == v_norm:
                return str(item["id"])
        if _is_uuid(v_str):
            return v_str
        return None

    def _safe_update(ctrl):
        """Dispara .update() no componente com segurança."""
        try:
            ctrl.update()
        except Exception:
            pass

    def _campo(label, hint="", keyboard=ft.KeyboardType.TEXT, prefix=None, valor="", on_change=None):
        kw = T.campo_estilo()
        if prefix:
            kw["prefix"] = prefix
        return ft.TextField(
            label=label,
            hint_text=hint,
            keyboard_type=keyboard,
            value=valor,
            on_change=on_change,
            **kw,
        )

    # Valores iniciais (edição ou novo)
    val_tipo = lanc_edit.get("tipo") if is_edicao else "Despesa"
    val_subtipo = lanc_edit.get("subtipo") if is_edicao else "Despesa"
    val_forma = lanc_edit.get("forma_movimentacao") if is_edicao else "Pix"
    val_valor = f"{float(lanc_edit.get('valor', 0)):.2f}".replace('.', ',') if is_edicao else "0,00"
    val_data = str(lanc_edit.get("data") or datetime.now().strftime("%Y-%m-%d")) if is_edicao else datetime.now().strftime("%Y-%m-%d")
    val_hora = str(lanc_edit.get("hora") if (is_edicao and lanc_edit.get("hora") is not None) else datetime.now().hour)
    val_desc = str(lanc_edit.get("descricao") or "") if is_edicao else ""
    val_conta = str(lanc_edit.get("cartao_id") or lanc_edit.get("conta_id") or (contas[0]["id"] if contas else "")) if is_edicao else (str(contas[0]["id"]) if contas else None)
    val_cat = str(lanc_edit.get("categoria_id") or (categorias_lista[0]["id"] if categorias_lista else "")) if is_edicao else (str(categorias_lista[0]["id"]) if categorias_lista else None)
    val_status = lanc_edit.get("status") if is_edicao and lanc_edit.get("status") else "Pago"
    val_regra = lanc_edit.get("regra") if is_edicao and lanc_edit.get("regra") else REGRAS_5030[0]

    # =========================================================================
    # CAMPOS PRINCIPAIS
    # =========================================================================
    dd_tipo = ft.Dropdown(
        label="Tipo *",
        value=val_tipo,
        options=[ft.dropdown.Option(t) for t in TIPOS_LANCAMENTO],
        **T.dropdown_estilo(),
    )

    dd_subtipo = ft.Dropdown(
        label="Subtipo *",
        value=val_subtipo,
        options=[ft.dropdown.Option(s) for s in (SUBTIPOS_RECEITA if "receit" in _norm(val_tipo) else (SUBTIPOS_TRANSFERENCIA if "trans" in _norm(val_tipo) else SUBTIPOS_DESPESA))],
        **T.dropdown_estilo(),
    )

    dd_forma = ft.Dropdown(
        label="Forma de Movimentação *",
        value=val_forma,
        options=[ft.dropdown.Option(f) for f in (FORMAS_RECEITA if "receit" in _norm(val_tipo) else (FORMAS_TRANSFERENCIA if "trans" in _norm(val_tipo) else FORMAS_DESPESA))],
        **T.dropdown_estilo(),
    )

    # Valores, Parcelas e Data
    txt_valor = _campo("Valor Total (R$)", "0,00", ft.KeyboardType.NUMBER, "R$ ", valor=val_valor)
    txt_num_parcelas = _campo("Qtd. Parcelas *", "Ex: 2", ft.KeyboardType.NUMBER, valor="1")
    txt_data = _campo("Data", "AAAA-MM-DD", valor=val_data)
    txt_hora = _campo("Hora", "Ex: 14", ft.KeyboardType.NUMBER, valor=val_hora)

    lbl_resumo_parcelamento = ft.Text(
        "Informe os dados do parcelamento",
        color=T.TEXT_MUTED,
        size=12,
        weight=ft.FontWeight.W_500,
    )

    row_resumo_parcelas = ft.Container(
        visible=False,
        padding=pad(h=12, v=8),
        bgcolor=T.SURFACE_ALT,
        border_radius=8,
        border=borda(),
        content=ft.Row([
            ft.Icon(ft.Icons.CALCULATE_OUTLINED, size=18, color=T.PRIMARY),
            lbl_resumo_parcelamento,
        ], spacing=8),
    )

    def recalcular_parcelas(_=None):
        try:
            val_total = float(txt_valor.value.replace(",", ".").replace("R$", "").strip() or 0)
            n_parc = int(txt_num_parcelas.value.strip() or 1)
            if n_parc <= 0:
                n_parc = 1
            if val_total > 0:
                parc = val_total / n_parc
                lbl_resumo_parcelamento.value = (
                    f"✓ Total: R$ {val_total:,.2f} dividido em {n_parc}x de R$ {parc:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                )
                lbl_resumo_parcelamento.color = T.RECEITA
            else:
                lbl_resumo_parcelamento.value = f"Informe o valor total para simular as {n_parc} parcelas"
                lbl_resumo_parcelamento.color = T.TEXT_MUTED
        except Exception:
            pass
        _safe_update(lbl_resumo_parcelamento)
        page.update()

    txt_valor.on_change = recalcular_parcelas
    txt_num_parcelas.on_change = recalcular_parcelas

    # Containers dos campos de valor e parcelas
    container_valor = ft.Container(content=txt_valor, col={"xs": 12, "sm": 4})
    container_parcelas = ft.Container(content=txt_num_parcelas, col={"xs": 12, "sm": 2}, visible=False)
    container_data = ft.Container(content=txt_data, col={"xs": 12, "sm": 4})
    container_hora = ft.Container(content=txt_hora, col={"xs": 12, "sm": 4})

    # Contas e Destino
    dd_conta = ft.Dropdown(
        label="Cartão de Crédito *" if (is_edicao and lanc_edit.get("cartao_id")) else "Conta *",
        options=_opts(cartoes if (is_edicao and lanc_edit.get("cartao_id")) else contas),
        value=val_conta,
        **T.dropdown_estilo(),
    )

    dd_destino = ft.Dropdown(
        label="Conta de Destino *",
        options=_opts(contas),
        value=str(lanc_edit.get("destino_id")) if (is_edicao and lanc_edit.get("destino_id")) else (str(contas[1]["id"]) if len(contas) > 1 else (str(contas[0]["id"]) if contas else None)),
        **T.dropdown_estilo(),
    )

    # Categorias e Subcategorias
    dd_categoria = ft.Dropdown(
        label="Categoria *",
        options=_opts(categorias_lista),
        value=val_cat,
        **T.dropdown_estilo(),
    )

    dd_subcategoria = ft.Dropdown(
        label="Subcategoria",
        hint_text="Selecione a categoria primeiro",
        disabled=False,
        options=[],
        **T.dropdown_estilo(),
    )

    # Status e Regra 50/30/20
    dd_status = ft.Dropdown(
        label="Status *",
        value=val_status,
        options=[ft.dropdown.Option(s) for s in STATUS_OPCOES],
        **T.dropdown_estilo(),
    )

    dd_regra = ft.Dropdown(
        label="Regra 50/30/20 *",
        value=val_regra,
        options=[ft.dropdown.Option(r) for r in REGRAS_5030],
        **T.dropdown_estilo(),
    )

    txt_desc = _campo("Descrição", "Ex: Aluguel de março, Notebook Dell...", valor=val_desc)

    container_regra = ft.Container(content=dd_regra, col={"xs": 12, "sm": 6}, visible=("desp" in _norm(val_tipo)))
    container_destino = ft.Container(content=dd_destino, col={"xs": 12, "sm": 6}, visible=("trans" in _norm(val_tipo)))
    container_status = ft.Container(content=dd_status, col={"xs": 12, "sm": 6}, visible=True)
    container_desc = ft.Container(content=txt_desc, col={"xs": 12, "sm": 6} if ("desp" in _norm(val_tipo)) else {"xs": 12})

    # =========================================================================
    # REATIVIDADE & EVENTOS EM CASCATA (.update() obrigatório)
    # =========================================================================
    def on_forma_change(e=None):
        """Listener de Forma de Movimentação -> Cartão de Crédito e Parcelas."""
        if e and hasattr(e, "data") and e.data is not None:
            dd_forma.value = e.data

        forma_n = _norm(dd_forma.value)
        tipo_n = _norm(dd_tipo.value)
        is_credito = ("cred" in forma_n) and ("desp" in tipo_n)
        is_transf = "trans" in tipo_n

        # 1. Altera Label e lista de Contas/Cartões
        dd_conta.value = None
        if is_credito:
            dd_conta.label = "Cartão de Crédito *"
            if cartoes:
                dd_conta.options = _opts(cartoes)
                dd_conta.value = str(cartoes[0]["id"])
                dd_conta.hint_text = "Selecione o Cartão"
            else:
                dd_conta.options = []
                dd_conta.value = None
                dd_conta.hint_text = "Nenhum cartão cadastrado"
        else:
            if is_transf:
                dd_conta.label = "Conta de Origem *"
            else:
                dd_conta.label = "Conta *"
            dd_conta.options = _opts(contas)
            if contas:
                dd_conta.value = str(contas[0]["id"])
            dd_conta.hint_text = "Selecione a Conta"

        # 2. Renderização Condicional dos campos de parcelas
        container_parcelas.visible = is_credito
        row_resumo_parcelas.visible = is_credito

        if is_credito:
            container_valor.col = {"xs": 12, "sm": 4}
            container_parcelas.col = {"xs": 12, "sm": 2}
            container_data.col = {"xs": 12, "sm": 3}
            container_hora.col = {"xs": 12, "sm": 3}
            recalcular_parcelas()
        else:
            container_valor.col = {"xs": 12, "sm": 4}
            container_data.col = {"xs": 12, "sm": 4}
            container_hora.col = {"xs": 12, "sm": 4}

        # 3. Dispara .update() nos componentes atualizados
        _safe_update(dd_conta)
        _safe_update(container_parcelas)
        _safe_update(row_resumo_parcelas)
        _safe_update(container_valor)
        _safe_update(container_data)
        _safe_update(container_hora)
        page.update()

    def on_tipo_change(e=None):
        """Listener de Tipo -> Subtipo e Formas de Movimentação."""
        if e and hasattr(e, "data") and e.data is not None:
            dd_tipo.value = e.data

        tipo_n = _norm(dd_tipo.value)
        is_despesa = "desp" in tipo_n
        is_transf = "trans" in tipo_n
        is_receita = "receit" in tipo_n

        # 1. Limpa valor atual do Subtipo
        dd_subtipo.value = None

        # 2. Filtra array de Subtipos válidos
        if is_transf:
            opcoes_sub = SUBTIPOS_TRANSFERENCIA
            opcoes_forma = FORMAS_TRANSFERENCIA
        elif is_receita:
            opcoes_sub = SUBTIPOS_RECEITA
            opcoes_forma = FORMAS_RECEITA
        else:
            opcoes_sub = SUBTIPOS_DESPESA
            opcoes_forma = FORMAS_DESPESA

        dd_subtipo.options = [ft.dropdown.Option(s) for s in opcoes_sub]
        dd_subtipo.value = opcoes_sub[0]

        # Atualiza opções de Forma
        forma_antiga = dd_forma.value
        dd_forma.options = [ft.dropdown.Option(f) for f in opcoes_forma]
        if forma_antiga in opcoes_forma:
            dd_forma.value = forma_antiga
        else:
            dd_forma.value = opcoes_forma[0]

        container_regra.visible = is_despesa
        container_destino.visible = is_transf
        container_desc.col = {"xs": 12, "sm": 6} if is_despesa else {"xs": 12}

        # 3. Dispara .update() nos componentes alterados
        _safe_update(dd_subtipo)
        _safe_update(dd_forma)
        _safe_update(container_regra)
        _safe_update(container_destino)
        _safe_update(container_desc)

        # Dispara lógica de Forma
        on_forma_change(None)
        page.update()

    def carregar_subcategorias(cat_id_ou_nome: str = None, selecionar_id: str = None):
        """Limpa valor da subcategoria e recarrega vinculadas ao pai."""
        dd_subcategoria.value = None
        dd_subcategoria.options = []

        cat_id = _obter_cat_id(cat_id_ou_nome or dd_categoria.value)

        if not cat_id or not _is_uuid(cat_id):
            dd_subcategoria.disabled = True
            dd_subcategoria.hint_text = "Selecione a categoria primeiro"
            _safe_update(dd_subcategoria)
            page.update()
            return

        try:
            subs = db.listar_subcategorias(categoria_id=cat_id)
            dd_subcategoria.disabled = False
            if subs:
                dd_subcategoria.options = [ft.dropdown.Option(key=str(s["id"]), text=s["nome"]) for s in subs]
                dd_subcategoria.hint_text = "Selecione a subcategoria"
                sel_id_str = _obter_subcat_id(selecionar_id, subs) if selecionar_id else None
                if sel_id_str and any(str(s["id"]) == sel_id_str for s in subs):
                    dd_subcategoria.value = sel_id_str
                else:
                    dd_subcategoria.value = str(subs[0]["id"])
            else:
                dd_subcategoria.options = []
                dd_subcategoria.value = None
                dd_subcategoria.hint_text = "Sem subcategorias (clique no +)"
        except Exception as ex:
            mostrar_feedback(page, f"Erro ao listar subcategorias: {ex}", "erro")

        _safe_update(dd_subcategoria)
        page.update()

    def on_categoria_change(e=None):
        """Listener de Categoria -> Subcategoria."""
        selected = e.data if (e and hasattr(e, "data") and e.data is not None) else dd_categoria.value
        cat_id = _obter_cat_id(selected)
        if cat_id:
            dd_categoria.value = cat_id
        carregar_subcategorias(cat_id)
        _safe_update(dd_categoria)

    def on_subcategoria_change(e=None):
        """Listener de seleção de Subcategoria."""
        if e and hasattr(e, "data") and e.data is not None:
            sub_id = _obter_subcat_id(e.data)
            if sub_id:
                dd_subcategoria.value = sub_id
                _safe_update(dd_subcategoria)

    def on_conta_change(e=None):
        """Listener de seleção de Conta / Cartão."""
        if e and hasattr(e, "data") and e.data is not None:
            c_id = _obter_conta_id(e.data)
            if c_id:
                dd_conta.value = c_id
                _safe_update(dd_conta)

    def on_destino_change(e=None):
        """Listener de seleção de Conta de Destino."""
        if e and hasattr(e, "data") and e.data is not None:
            c_id = _obter_conta_id(e.data, contas)
            if c_id:
                dd_destino.value = c_id
                _safe_update(dd_destino)

    def on_subtipo_change(e=None):
        """Listener de seleção de Subtipo."""
        if e and hasattr(e, "data") and e.data is not None:
            dd_subtipo.value = e.data
            _safe_update(dd_subtipo)

    # Conecta listeners usando on_select (Flet 1.0.1 oficial para DropdownMenu)
    dd_tipo.on_select = on_tipo_change
    dd_forma.on_select = on_forma_change
    dd_subtipo.on_select = on_subtipo_change
    dd_categoria.on_select = on_categoria_change
    dd_subcategoria.on_select = on_subcategoria_change
    dd_conta.on_select = on_conta_change
    dd_destino.on_select = on_destino_change

    # =========================================================================
    # MODAIS DE CRIAÇÃO INLINE (+)
    # =========================================================================
    def abrir_modal_novo_subtipo(_):
        txt_nome = ft.TextField(
            label="Nome do Subtipo *",
            hint_text="Ex: Rendimento, Bônus, Assinatura...",
            autofocus=True,
            **T.campo_estilo(),
        )

        def salvar_subtipo(_):
            nome = txt_nome.value.strip()
            if not nome:
                mostrar_feedback(page, "Informe o nome do subtipo.", "alerta")
                return
            if not any(opt.key == nome for opt in dd_subtipo.options):
                dd_subtipo.options.append(ft.dropdown.Option(nome))
            dd_subtipo.value = nome
            modal_subtipo.open = False
            _safe_update(dd_subtipo)
            page.update()
            mostrar_feedback(page, f"Subtipo '{nome}' selecionado!", "sucesso")

        modal_subtipo = ft.AlertDialog(
            title=ft.Row([
                ft.Icon(ft.Icons.LABEL_ROUNDED, color=T.PRIMARY, size=22),
                ft.Text("Novo Subtipo", size=18, weight=ft.FontWeight.BOLD),
            ], spacing=8),
            content=ft.Column(spacing=12, tight=True, controls=[
                ft.Text("Adicione uma classificação personalizada para este lançamento.", color=T.TEXT_MUTED, size=12),
                txt_nome,
            ]),
            actions=[
                ft.TextButton(
                    content=ft.Text("Cancelar", color=T.TEXT_MUTED),
                    on_click=lambda _: (setattr(modal_subtipo, "open", False), page.update()),
                ),
                ft.FilledButton(
                    content=ft.Text("Adicionar"),
                    style=ft.ButtonStyle(bgcolor=T.PRIMARY),
                    on_click=salvar_subtipo,
                ),
            ],
        )
        page.overlay.append(modal_subtipo)
        modal_subtipo.open = True
        page.update()

    def abrir_modal_nova_categoria(_):
        txt_nome_cat = ft.TextField(
            label="Nome da Categoria *",
            hint_text="Ex: Alimentação, DJ, Investimento",
            autofocus=True,
            **T.campo_estilo(),
        )

        def salvar_nova_cat(_):
            nome = txt_nome_cat.value.strip()
            if not nome:
                mostrar_feedback(page, "Informe o nome da categoria.", "alerta")
                return
            try:
                nova = db.criar_categoria({"nome": nome, "tipo": "ambos", "cor": T.PRIMARY, "icone": "category"})
                modal_cat.open = False
                page.update()

                novas_cats = db.listar_categorias()
                categorias_lista.clear()
                categorias_lista.extend(novas_cats)
                dd_categoria.options = _opts(novas_cats)

                if nova and nova.data:
                    novo_id = str(nova.data[0]["id"])
                    dd_categoria.value = novo_id
                    carregar_subcategorias(novo_id)

                _safe_update(dd_categoria)
                mostrar_feedback(page, f"Categoria '{nome}' criada com sucesso!", "sucesso")
            except Exception as ex:
                mostrar_feedback(page, f"Erro ao criar categoria: {ex}", "erro")

        modal_cat = ft.AlertDialog(
            title=ft.Row([
                ft.Icon(ft.Icons.CATEGORY_ROUNDED, color=T.PRIMARY, size=22),
                ft.Text("Nova Categoria Universal", size=18, weight=ft.FontWeight.BOLD),
            ], spacing=8),
            content=ft.Column(spacing=12, tight=True, controls=[
                ft.Text("Categorias universais podem ser usadas para Receitas e Despesas.", color=T.TEXT_MUTED, size=12),
                txt_nome_cat,
            ]),
            actions=[
                ft.TextButton(
                    content=ft.Text("Cancelar", color=T.TEXT_MUTED),
                    on_click=lambda _: (setattr(modal_cat, "open", False), page.update()),
                ),
                ft.FilledButton(
                    content=ft.Text("Criar Categoria"),
                    style=ft.ButtonStyle(bgcolor=T.PRIMARY),
                    on_click=salvar_nova_cat,
                ),
            ],
        )
        page.overlay.append(modal_cat)
        modal_cat.open = True
        page.update()

    def abrir_modal_nova_subcategoria(_):
        cat_id = _obter_cat_id(dd_categoria.value)
        if not cat_id:
            mostrar_feedback(page, "Selecione uma Categoria primeiro para vincular a Subcategoria.", "alerta")
            return

        cat_nome = next((opt.text for opt in dd_categoria.options if opt.key == cat_id), "Categoria Selecionada")

        txt_nome_sub = ft.TextField(
            label="Nome da Subcategoria *",
            hint_text="Ex: Notebook, Gasolina, Cursos...",
            autofocus=True,
            **T.campo_estilo(),
        )

        def salvar_nova_sub(_):
            nome = txt_nome_sub.value.strip()
            if not nome:
                mostrar_feedback(page, "Informe o nome da subcategoria.", "alerta")
                return
            try:
                nova_sub = db.criar_subcategoria(categoria_id=cat_id, nome=nome)
                modal_sub.open = False
                page.update()

                novo_sub_id = str(nova_sub.data[0]["id"]) if (nova_sub and nova_sub.data) else None
                carregar_subcategorias(cat_id, selecionar_id=novo_sub_id)
                mostrar_feedback(page, f"Subcategoria '{nome}' vinculada a '{cat_nome}' criada!", "sucesso")
            except Exception as ex:
                mostrar_feedback(page, f"Erro ao criar subcategoria: {ex}", "erro")

        modal_sub = ft.AlertDialog(
            title=ft.Row([
                ft.Icon(ft.Icons.SUBDIRECTORY_ARROW_RIGHT_ROUNDED, color=T.PRIMARY, size=22),
                ft.Text("Nova Subcategoria", size=18, weight=ft.FontWeight.BOLD),
            ], spacing=8),
            content=ft.Column(spacing=12, tight=True, controls=[
                ft.Container(
                    content=ft.Row([
                        ft.Text("Categoria Pai:", color=T.TEXT_MUTED, size=12),
                        ft.Text(cat_nome, color=T.PRIMARY, size=13, weight=ft.FontWeight.BOLD),
                    ], spacing=6),
                    padding=pad(h=12, v=8),
                    bgcolor=T.SURFACE_ALT,
                    border_radius=8,
                    border=borda(),
                ),
                txt_nome_sub,
            ]),
            actions=[
                ft.TextButton(
                    content=ft.Text("Cancelar", color=T.TEXT_MUTED),
                    on_click=lambda _: (setattr(modal_sub, "open", False), page.update()),
                ),
                ft.FilledButton(
                    content=ft.Text("Criar Subcategoria"),
                    style=ft.ButtonStyle(bgcolor=T.PRIMARY),
                    on_click=salvar_nova_sub,
                ),
            ],
        )
        page.overlay.append(modal_sub)
        modal_sub.open = True
        page.update()

    # =========================================================================
    # COMPONENTE: [Dropdown, Botão] em ft.Row com MainAxisAlignment.START e spacing=10
    # O botão fica colado ao lado direito do campo, sem vazar para a extrema direita.
    # =========================================================================
    def _campo_com_add(dropdown: ft.Dropdown, tooltip: str, on_click, width: int = 240) -> ft.Row:
        dropdown.width = width
        return ft.Row(
            alignment=ft.MainAxisAlignment.START,
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                dropdown,
                ft.IconButton(
                    icon=ft.Icons.ADD_ROUNDED,
                    icon_color=ft.Colors.WHITE,
                    icon_size=20,
                    tooltip=tooltip,
                    on_click=on_click,
                    style=ft.ButtonStyle(
                        bgcolor=T.PRIMARY,
                        shape=ft.RoundedRectangleBorder(radius=10),
                        padding=pad(all_=10),
                    ),
                ),
            ],
        )

    campo_subtipo_inline = _campo_com_add(dd_subtipo, "Adicionar Subtipo", abrir_modal_novo_subtipo, width=240)
    campo_categoria_inline = _campo_com_add(dd_categoria, "Adicionar Categoria", abrir_modal_nova_categoria, width=280)
    campo_subcategoria_inline = _campo_com_add(dd_subcategoria, "Adicionar Subcategoria", abrir_modal_nova_subcategoria, width=280)

    # =========================================================================
    # SALVAR LANÇAMENTO
    # =========================================================================
    spinner_s = ft.ProgressRing(color=ft.Colors.WHITE, width=18, height=18, stroke_width=2, visible=False)
    txt_btn_s = ft.Text(
        "Atualizar Lançamento" if is_edicao else "Salvar Lançamento",
        color=ft.Colors.WHITE,
        size=14,
        weight=ft.FontWeight.W_600,
    )

    def on_salvar(_):
        erros = []
        try:
            v = float(txt_valor.value.replace(",", ".").replace("R$", "").strip() or 0)
        except ValueError:
            v = 0

        if v <= 0:
            erros.append("Informe um valor válido maior que zero.")
        if not txt_data.value:
            erros.append("Informe a data.")

        tipo_str = _norm(dd_tipo.value)
        forma_str = _norm(dd_forma.value)
        is_despesa = "desp" in tipo_str
        is_transf = "trans" in tipo_str
        is_credito = is_despesa and ("cred" in forma_str)

        cat_id_salvar = _obter_cat_id(dd_categoria.value)
        subcat_id_salvar = _obter_subcat_id(dd_subcategoria.value)
        conta_id_salvar = _obter_conta_id(dd_conta.value)
        destino_id_salvar = _obter_conta_id(dd_destino.value, contas)

        if is_transf:
            if not conta_id_salvar:
                erros.append("Selecione a Conta de Origem.")
            if not destino_id_salvar:
                erros.append("Selecione a Conta de Destino.")
            if conta_id_salvar and destino_id_salvar and conta_id_salvar == destino_id_salvar:
                erros.append("A Conta de Origem e Destino devem ser diferentes.")
        else:
            if not conta_id_salvar:
                erros.append("Selecione o Cartão de Crédito." if is_credito else "Selecione a Conta.")
            if not cat_id_salvar:
                erros.append("Selecione uma Categoria.")
            if is_despesa and not dd_regra.value:
                erros.append("Selecione a Regra 50/30/20.")

        if erros:
            mostrar_feedback(page, " | ".join(erros), "alerta")
            return

        spinner_s.visible = True
        page.update()

        try:
            dados = {
                "tipo": dd_tipo.value,
                "subtipo": dd_subtipo.value or dd_tipo.value,
                "forma_movimentacao": dd_forma.value,
                "conta_id": conta_id_salvar if not is_credito else None,
                "cartao_id": conta_id_salvar if is_credito else None,
                "destino_id": destino_id_salvar if is_transf else None,
                "categoria_id": cat_id_salvar if not is_transf else None,
                "subcategoria_id": subcat_id_salvar if not is_transf else None,
                "valor": v,
                "data": txt_data.value,
                "hora": int(txt_hora.value or 0),
                "descricao": txt_desc.value.strip() if txt_desc.value else (
                    f"Transferência" if is_transf else "Lançamento"
                ),
                "status": dd_status.value if not is_transf else "Pago",
                "regra": dd_regra.value if is_despesa else None,
            }

            if is_edicao:
                db.atualizar_lancamento(edit_id, dados)
                session_remove(page, "edit_lancamento_id")
                session_remove(page, "edit_lancamento_dados")
                mostrar_feedback(page, "Lançamento atualizado com sucesso!", "sucesso")
                navegar(page, ROTA_RELATORIOS)
            else:
                # Lógica de parcelas no crédito
                if is_credito:
                    total_parcelas = int(txt_num_parcelas.value or 1)
                    if total_parcelas > 1:
                        base_date = datetime.strptime(dados["data"], "%Y-%m-%d")
                        valor_total = dados["valor"]
                        valor_parcela = round(valor_total / total_parcelas, 2)
                        for i in range(total_parcelas):
                            d_parc = dados.copy()
                            d_parc["parcela_atual"] = i + 1
                            d_parc["total_parcelas"] = total_parcelas
                            d_parc["valor"] = valor_parcela
                            next_date = base_date + relativedelta(months=i)
                            d_parc["data"] = next_date.strftime("%Y-%m-%d")
                            db.criar_lancamento(d_parc)
                    else:
                        dados["parcela_atual"] = 1
                        dados["total_parcelas"] = 1
                        db.criar_lancamento(dados)
                else:
                    db.criar_lancamento(dados)

                mostrar_feedback(page, "Lançamento salvo com sucesso!", "sucesso")
                navegar(page, ROTA_DASHBOARD)
        except Exception as ex:
            mostrar_feedback(page, f"Erro ao salvar: {ex}", "erro")
        finally:
            spinner_s.visible = False
            page.update()

    btn_salvar = ft.FilledButton(
        content=ft.Row([spinner_s, txt_btn_s], alignment=ft.MainAxisAlignment.CENTER, spacing=10, tight=True),
        on_click=on_salvar,
        expand=True,
        style=ft.ButtonStyle(
            bgcolor=T.PRIMARY,
            overlay_color=T.PRIMARY_DARK,
            shape=ft.RoundedRectangleBorder(radius=10),
            padding=pad(h=24, v=16),
        ),
    )

    def _ao_cancelar_voltar(_):
        session_remove(page, "edit_lancamento_id")
        session_remove(page, "edit_lancamento_dados")
        navegar(page, ROTA_RELATORIOS if is_edicao else ROTA_DASHBOARD)

    btn_cancelar = T.botao_outline(
        "Cancelar",
        on_click=_ao_cancelar_voltar,
        icone=ft.Icons.ARROW_BACK_ROUNDED,
    )

    # =========================================================================
    # LAYOUT GRID RESPONSIVO
    # =========================================================================
    corpo = ft.Column(
        scroll=ft.ScrollMode.AUTO,
        expand=True,
        spacing=0,
        controls=[
            # Cabeçalho
            ft.Row(spacing=8, controls=[
                ft.IconButton(
                    icon=ft.Icons.ARROW_BACK_IOS_NEW_ROUNDED,
                    icon_color=T.TEXT_MUTED,
                    on_click=_ao_cancelar_voltar,
                ),
                ft.Column(spacing=2, controls=[
                    ft.Text("Editar Lançamento" if is_edicao else "Novo Lançamento", color=T.TEXT_PRIMARY, size=22, weight=ft.FontWeight.BOLD),
                    ft.Text("Atualize os dados da transação financeira" if is_edicao else "Preencha os dados do lançamento financeiro", color=T.TEXT_MUTED, size=12),
                ]),
            ]),
            ft.Container(height=16),

            # Card Principal
            ft.Container(
                padding=pad(all_=24),
                bgcolor=T.SURFACE,
                border_radius=16,
                border=borda(),
                content=ft.Column(spacing=16, controls=[
                    # 1. Classificação Principal
                    ft.Text("Classificação Principal", color=T.TEXT_MUTED, size=12, weight=ft.FontWeight.W_600),
                    ft.ResponsiveRow(spacing=12, run_spacing=12, controls=[
                        ft.Container(content=dd_tipo,               col={"xs": 12, "sm": 4}),
                        ft.Container(content=campo_subtipo_inline,  col={"xs": 12, "sm": 4}),
                        ft.Container(content=dd_forma,              col={"xs": 12, "sm": 4}),
                    ]),

                    ft.Divider(color=T.BORDER, height=10),

                    # 2. Valores e Data (com campo de parcelas condicional lado a lado)
                    ft.Text("Valores e Informações de Data", color=T.TEXT_MUTED, size=12, weight=ft.FontWeight.W_600),
                    ft.ResponsiveRow(spacing=12, run_spacing=12, controls=[
                        container_valor,
                        container_parcelas,
                        container_data,
                        container_hora,
                    ]),
                    row_resumo_parcelas,
                    ft.Divider(color=T.BORDER, height=10),

                    # 3. Contas e Categorias
                    ft.Text("Contas e Categorias", color=T.TEXT_MUTED, size=12, weight=ft.FontWeight.W_600),
                    ft.ResponsiveRow(spacing=12, run_spacing=12, controls=[
                        ft.Container(content=dd_conta,          col={"xs": 12, "sm": 6}),
                        container_destino,
                        container_status,
                    ]),
                    ft.ResponsiveRow(spacing=12, run_spacing=12, controls=[
                        ft.Container(content=campo_categoria_inline,    col={"xs": 12, "sm": 6}),
                        ft.Container(content=campo_subcategoria_inline, col={"xs": 12, "sm": 6}),
                    ]),
                    ft.ResponsiveRow(spacing=12, run_spacing=12, controls=[
                        container_desc,
                        container_regra,
                    ]),
                    ft.Divider(color=T.BORDER, height=20),

                    # Botões de Ação
                    ft.ResponsiveRow(spacing=12, run_spacing=12, controls=[
                        ft.Container(content=btn_cancelar, col={"xs": 12, "sm": 4}),
                        ft.Container(content=btn_salvar,   col={"xs": 12, "sm": 8}),
                    ]),
                ]),
            ),
            ft.Container(height=40),  # Respiro inferior para rolagem sem cortes
        ],
    )

    # Inicializar subcategorias da primeira categoria
    if dd_categoria.value:
        carregar_subcategorias(dd_categoria.value)

    return ft.View(
        route="/lancamento",
        bgcolor=T.BG,
        padding=pad(all_=20),
        controls=[corpo],
    )
