"""
=============================================================================
DemBase v3 — views/config_view.py  (Flet 1.0.1)
Configurações do Usuário e CRUDs Base (Perfil, Categorias, Destinos).
Montado DENTRO do Shell (sidebar + header).
=============================================================================
"""
import flet as ft
from core import theme as T
from core.theme import pad, borda, mostrar_feedback
from core.router import ROTA_CONFIG, ROTA_AUTH, navegar
from views.shell_view import criar_shell
import services.supabase_client as db

CATEGORIAS_PADRAO = [
    {"nome": "Alimentação",  "tipo": "ambos", "cor": "#EF4444", "icone": "restaurant"},
    {"nome": "Transporte",   "tipo": "ambos", "cor": "#3B82F6", "icone": "directions_car"},
    {"nome": "Moradia",      "tipo": "ambos", "cor": "#8B5CF6", "icone": "home"},
    {"nome": "Lazer",        "tipo": "ambos", "cor": "#F59E0B", "icone": "celebration"},
    {"nome": "Saúde",        "tipo": "ambos", "cor": "#10B981", "icone": "medical_services"},
    {"nome": "Educação",     "tipo": "ambos", "cor": "#06B6D4", "icone": "school"},
    {"nome": "DJ & Eventos", "tipo": "ambos", "cor": "#EC4899", "icone": "headphones"},
    {"nome": "Investimento", "tipo": "ambos", "cor": "#10B981", "icone": "trending_up"},
    {"nome": "Salário",      "tipo": "ambos", "cor": "#10B981", "icone": "payments"},
    {"nome": "Outros",       "tipo": "ambos", "cor": "#64748B", "icone": "more_horiz"},
]

DESTINOS_PADRAO = ["Eu", "Casa", "Moto", "Carro", "DJ", "Família", "Outros"]


def criar_view_config(page: ft.Page) -> ft.View:
    aba_ativa = [0]  # 0: Perfil, 1: Categorias, 2: Destinos
    spinner = ft.ProgressRing(color=T.PRIMARY, width=20, height=20, stroke_width=2, visible=False)

    area_conteudo = ft.Column(spacing=16, controls=[])

    # ── 1. ABA PERFIL ────────────────────────────────────────────────────────
    def _montar_aba_perfil():
        user = db.usuario_atual()
        email_str = user.email if user and user.email else "E-mail não informado"

        perfil_db = {}
        try:
            perfil_db = db.ler_perfil() or {}
        except Exception:
            pass

        nome_atual = perfil_db.get("nome", "")
        if not nome_atual and user and hasattr(user, "user_metadata"):
            nome_atual = user.user_metadata.get("full_name", "")

        txt_nome = ft.TextField(
            label="Nome Completo",
            value=nome_atual,
            **T.campo_estilo(),
        )

        txt_email = ft.TextField(
            label="E-mail de Acesso",
            value=email_str,
            read_only=True,
            disabled=True,
            **T.campo_estilo(),
        )

        def salvar_perfil(_):
            nome_novo = txt_nome.value.strip()
            if not nome_novo:
                mostrar_feedback(page, "Informe o nome.", "alerta")
                return
            try:
                db.atualizar_perfil({"nome": nome_novo})
                mostrar_feedback(page, "Perfil atualizado com sucesso!", "sucesso")
            except Exception as ex:
                mostrar_feedback(page, f"Erro ao atualizar perfil: {ex}", "erro")

        def sair_app(_):
            try:
                db.fazer_logout()
            except Exception:
                pass
            navegar(page, ROTA_AUTH)

        return ft.Container(
            padding=pad(all_=24),
            bgcolor=T.SURFACE,
            border_radius=16,
            border=borda(),
            content=ft.Column(
                spacing=16,
                controls=[
                    ft.Row(
                        spacing=16,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.CircleAvatar(
                                radius=32,
                                bgcolor=T.PRIMARY,
                                content=ft.Text(nome_atual[0].upper() if nome_atual else "U", size=24, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                            ),
                            ft.Column(
                                spacing=2,
                                controls=[
                                    ft.Text(nome_atual or "Usuário DemBase", color=T.TEXT_PRIMARY, size=18, weight=ft.FontWeight.BOLD),
                                    ft.Text(email_str, color=T.TEXT_MUTED, size=13),
                                ],
                            ),
                        ],
                    ),
                    ft.Divider(color=T.BORDER, height=16),
                    ft.Text("Dados Cadastrais", color=T.TEXT_PRIMARY, size=14, weight=ft.FontWeight.BOLD),
                    txt_nome,
                    txt_email,
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.OutlinedButton(
                                content=ft.Row([ft.Icon(ft.Icons.LOGOUT_ROUNDED, size=16, color=T.DESPESA), ft.Text("Desconectar Conta", color=T.DESPESA)]),
                                style=ft.ButtonStyle(side=ft.BorderSide(1, T.DESPESA)),
                                on_click=sair_app,
                            ),
                            ft.FilledButton(
                                content=ft.Row([ft.Icon(ft.Icons.CHECK_ROUNDED, size=16), ft.Text("Salvar Perfil")]),
                                style=ft.ButtonStyle(bgcolor=T.PRIMARY),
                                on_click=salvar_perfil,
                            ),
                        ],
                    ),
                ],
            ),
        )

    # ── 2. ABA CATEGORIAS ────────────────────────────────────────────────────
    def _montar_aba_categorias():
        col_itens = ft.Column(spacing=8, controls=[])

        def carregar_itens():
            col_itens.controls.clear()
            try:
                categorias = db.listar_categorias()
                if not categorias:
                    col_itens.controls.append(
                        ft.Container(
                            padding=pad(all_=30),
                            alignment=ft.Alignment(0, 0),
                            content=ft.Column(
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                spacing=10,
                                controls=[
                                    ft.Icon(ft.Icons.CATEGORY_OUTLINED, size=48, color=T.TEXT_MUTED),
                                    ft.Text("Nenhuma categoria encontrada", color=T.TEXT_PRIMARY, size=15, weight=ft.FontWeight.BOLD),
                                    ft.Text("Clique abaixo para carregar as categorias padrão do DemBase.", color=T.TEXT_MUTED, size=12),
                                    ft.FilledButton(
                                        content=ft.Text("⚡ Carregar Categorias Padrão"),
                                        style=ft.ButtonStyle(bgcolor=T.PRIMARY),
                                        on_click=carregar_padrao,
                                    ),
                                ],
                            ),
                        )
                    )
                else:
                    for cat in categorias:
                        cor_cat = cat.get("cor") or T.PRIMARY
                        tipo_str = cat.get("tipo", "ambos").capitalize()

                        def _excluir(c_id=cat["id"]):
                            try:
                                db.deletar_categoria(c_id)
                                mostrar_feedback(page, "Categoria inativada!", "sucesso")
                                carregar_itens()
                            except Exception as ex:
                                mostrar_feedback(page, f"Erro: {ex}", "erro")

                        item_row = ft.Container(
                            padding=pad(h=14, v=10),
                            bgcolor=T.SURFACE_ALT,
                            border_radius=10,
                            border=borda(),
                            content=ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    ft.Row(
                                        spacing=10,
                                        controls=[
                                            ft.Container(width=12, height=12, bgcolor=cor_cat, border_radius=6),
                                            ft.Text(cat.get("nome", ""), color=T.TEXT_PRIMARY, size=14, weight=ft.FontWeight.W_500),
                                            ft.Container(
                                                content=ft.Text(tipo_str, size=10, color=T.TEXT_MUTED),
                                                bgcolor=T.SURFACE,
                                                padding=pad(h=8, v=2),
                                                border_radius=6,
                                            ),
                                        ],
                                    ),
                                    ft.IconButton(
                                        icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                                        icon_color=T.TEXT_MUTED,
                                        icon_size=18,
                                        tooltip="Inativar",
                                        on_click=lambda _, cid=cat["id"]: _excluir(cid),
                                    ),
                                ],
                            ),
                        )
                        col_itens.controls.append(item_row)
                page.update()
            except Exception as ex:
                mostrar_feedback(page, f"Erro ao listar categorias: {ex}", "erro")

        def carregar_padrao(_):
            spinner.visible = True
            page.update()
            inseridos = 0
            for c in CATEGORIAS_PADRAO:
                try:
                    db.criar_categoria(c)
                    inseridos += 1
                except Exception:
                    pass
            spinner.visible = False
            mostrar_feedback(page, f"{inseridos} categorias padrão carregadas com sucesso!", "sucesso")
            carregar_itens()

        def abrir_modal_nova_categoria(_):
            txt_nome_cat = ft.TextField(label="Nome da Categoria *", hint_text="Ex: Alimentação, Academia", **T.campo_estilo())
            dd_tipo_cat = ft.Dropdown(
                label="Tipo *",
                options=[ft.dropdown.Option("despesa", "Despesa"), ft.dropdown.Option("receita", "Receita"), ft.dropdown.Option("ambos", "Ambos")],
                value="ambos",
                **T.dropdown_estilo(),
            )

            def salvar_cat(_):
                nome = txt_nome_cat.value.strip()
                if not nome:
                    mostrar_feedback(page, "Informe o nome.", "alerta")
                    return
                try:
                    db.criar_categoria({"nome": nome, "tipo": dd_tipo_cat.value, "cor": T.PRIMARY, "icone": "category"})
                    modal_cat.open = False
                    page.update()
                    mostrar_feedback(page, "Categoria criada com sucesso!", "sucesso")
                    carregar_itens()
                except Exception as ex:
                    mostrar_feedback(page, f"Erro ao criar categoria: {ex}", "erro")

            modal_cat = ft.AlertDialog(
                title=ft.Text("Nova Categoria", color=T.TEXT_PRIMARY, size=18, weight=ft.FontWeight.BOLD),
                content=ft.Column(spacing=12, tight=True, controls=[txt_nome_cat, dd_tipo_cat]),
                actions=[
                    ft.TextButton(content=ft.Text("Cancelar", color=T.TEXT_MUTED), on_click=lambda _: (setattr(modal_cat, "open", False), page.update())),
                    ft.FilledButton(content=ft.Text("Salvar"), style=ft.ButtonStyle(bgcolor=T.PRIMARY), on_click=salvar_cat),
                ],
            )
            page.overlay.append(modal_cat)
            modal_cat.open = True
            page.update()

        carregar_itens()

        return ft.Container(
            padding=pad(all_=20),
            bgcolor=T.SURFACE,
            border_radius=16,
            border=borda(),
            content=ft.Column(
                spacing=14,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Text("Categorias Cadastradas", color=T.TEXT_PRIMARY, size=16, weight=ft.FontWeight.BOLD),
                            ft.Row(
                                spacing=8,
                                controls=[
                                    ft.OutlinedButton(content=ft.Text("Carregar Padrão"), on_click=carregar_padrao),
                                    ft.FilledButton(
                                        content=ft.Row([ft.Icon(ft.Icons.ADD_ROUNDED, size=16), ft.Text("Nova Categoria")]),
                                        style=ft.ButtonStyle(bgcolor=T.PRIMARY),
                                        on_click=abrir_modal_nova_categoria,
                                    ),
                                ],
                            ),
                        ],
                    ),
                    ft.Divider(color=T.BORDER, height=1),
                    col_itens,
                ],
            ),
        )

    # ── 3. ABA DESTINOS ──────────────────────────────────────────────────────
    def _montar_aba_destinos():
        col_itens_dest = ft.Column(spacing=8, controls=[])

        def carregar_destinos():
            col_itens_dest.controls.clear()
            try:
                destinos = db.listar_destinos()
                if not destinos:
                    col_itens_dest.controls.append(
                        ft.Container(
                            padding=pad(all_=30),
                            alignment=ft.Alignment(0, 0),
                            content=ft.Column(
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                spacing=10,
                                controls=[
                                    ft.Icon(ft.Icons.SHARE_LOCATION_ROUNDED, size=48, color=T.TEXT_MUTED),
                                    ft.Text("Nenhum destino cadastrado", color=T.TEXT_PRIMARY, size=15, weight=ft.FontWeight.BOLD),
                                    ft.Text("Cadastre para quem ou onde o dinheiro está sendo direcionado (Eu, Casa, Moto, Família, DJ).", color=T.TEXT_MUTED, size=12),
                                    ft.FilledButton(
                                        content=ft.Text("⚡ Carregar Destinos Padrão"),
                                        style=ft.ButtonStyle(bgcolor=T.PRIMARY),
                                        on_click=carregar_padrao_dest,
                                    ),
                                ],
                            ),
                        )
                    )
                else:
                    for dest in destinos:
                        def _excluir(d_id=dest["id"]):
                            try:
                                db.deletar_destino(d_id)
                                mostrar_feedback(page, "Destino inativado!", "sucesso")
                                carregar_destinos()
                            except Exception as ex:
                                mostrar_feedback(page, f"Erro: {ex}", "erro")

                        item_row = ft.Container(
                            padding=pad(h=14, v=10),
                            bgcolor=T.SURFACE_ALT,
                            border_radius=10,
                            border=borda(),
                            content=ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    ft.Row(
                                        spacing=10,
                                        controls=[
                                            ft.Icon(ft.Icons.TRIP_ORIGIN_ROUNDED, color=T.PRIMARY, size=16),
                                            ft.Text(dest.get("nome", ""), color=T.TEXT_PRIMARY, size=14, weight=ft.FontWeight.W_500),
                                        ],
                                    ),
                                    ft.IconButton(
                                        icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                                        icon_color=T.TEXT_MUTED,
                                        icon_size=18,
                                        tooltip="Inativar",
                                        on_click=lambda _, did=dest["id"]: _excluir(did),
                                    ),
                                ],
                            ),
                        )
                        col_itens_dest.controls.append(item_row)
                page.update()
            except Exception as ex:
                mostrar_feedback(page, f"Erro ao listar destinos: {ex}", "erro")

        def carregar_padrao_dest(_):
            spinner.visible = True
            page.update()
            inseridos = 0
            for nome_dest in DESTINOS_PADRAO:
                try:
                    db.criar_destino(nome_dest)
                    inseridos += 1
                except Exception:
                    pass
            spinner.visible = False
            mostrar_feedback(page, f"{inseridos} destinos padrão carregados com sucesso!", "sucesso")
            carregar_destinos()

        def abrir_modal_novo_destino(_):
            txt_nome_dest = ft.TextField(label="Nome do Destino *", hint_text="Ex: Eu, Casa, DJ, Carro", **T.campo_estilo())

            def salvar_dest(_):
                nome = txt_nome_dest.value.strip()
                if not nome:
                    mostrar_feedback(page, "Informe o nome.", "alerta")
                    return
                try:
                    db.criar_destino(nome)
                    modal_dest.open = False
                    page.update()
                    mostrar_feedback(page, "Destino criado com sucesso!", "sucesso")
                    carregar_destinos()
                except Exception as ex:
                    mostrar_feedback(page, f"Erro ao criar destino: {ex}", "erro")

            modal_dest = ft.AlertDialog(
                title=ft.Text("Novo Destino", color=T.TEXT_PRIMARY, size=18, weight=ft.FontWeight.BOLD),
                content=ft.Column(spacing=12, tight=True, controls=[txt_nome_dest]),
                actions=[
                    ft.TextButton(content=ft.Text("Cancelar", color=T.TEXT_MUTED), on_click=lambda _: (setattr(modal_dest, "open", False), page.update())),
                    ft.FilledButton(content=ft.Text("Salvar"), style=ft.ButtonStyle(bgcolor=T.PRIMARY), on_click=salvar_dest),
                ],
            )
            page.overlay.append(modal_dest)
            modal_dest.open = True
            page.update()

        carregar_destinos()

        return ft.Container(
            padding=pad(all_=20),
            bgcolor=T.SURFACE,
            border_radius=16,
            border=borda(),
            content=ft.Column(
                spacing=14,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Text("Destinos Cadastrados", color=T.TEXT_PRIMARY, size=16, weight=ft.FontWeight.BOLD),
                            ft.Row(
                                spacing=8,
                                controls=[
                                    ft.OutlinedButton(content=ft.Text("Carregar Padrão"), on_click=carregar_padrao_dest),
                                    ft.FilledButton(
                                        content=ft.Row([ft.Icon(ft.Icons.ADD_ROUNDED, size=16), ft.Text("Novo Destino")]),
                                        style=ft.ButtonStyle(bgcolor=T.PRIMARY),
                                        on_click=abrir_modal_novo_destino,
                                    ),
                                ],
                            ),
                        ],
                    ),
                    ft.Divider(color=T.BORDER, height=1),
                    col_itens_dest,
                ],
            ),
        )

    # ── Alternar Abas ────────────────────────────────────────────────────────
    def renderizar_aba():
        area_conteudo.controls.clear()
        if aba_ativa[0] == 0:
            area_conteudo.controls.append(_montar_aba_perfil())
        elif aba_ativa[0] == 1:
            area_conteudo.controls.append(_montar_aba_categorias())
        else:
            area_conteudo.controls.append(_montar_aba_destinos())
        page.update()

    def _trocar_aba(idx: int):
        aba_ativa[0] = idx
        btn_perfil.bgcolor     = f"{T.PRIMARY}18" if idx == 0 else "transparent"
        btn_categorias.bgcolor = f"{T.PRIMARY}18" if idx == 1 else "transparent"
        btn_destinos.bgcolor   = f"{T.PRIMARY}18" if idx == 2 else "transparent"
        renderizar_aba()

    btn_perfil = ft.Container(
        content=ft.Row([ft.Icon(ft.Icons.PERSON_OUTLINED, size=16), ft.Text("Meu Perfil", size=13, weight=ft.FontWeight.W_600)], tight=True),
        padding=pad(h=16, v=10),
        bgcolor=f"{T.PRIMARY}18",
        border_radius=10,
        on_click=lambda _: _trocar_aba(0),
    )

    btn_categorias = ft.Container(
        content=ft.Row([ft.Icon(ft.Icons.CATEGORY_OUTLINED, size=16), ft.Text("Categorias", size=13, weight=ft.FontWeight.W_600)], tight=True),
        padding=pad(h=16, v=10),
        bgcolor="transparent",
        border_radius=10,
        on_click=lambda _: _trocar_aba(1),
    )

    btn_destinos = ft.Container(
        content=ft.Row([ft.Icon(ft.Icons.LOCATION_ON_OUTLINED, size=16), ft.Text("Destinos", size=13, weight=ft.FontWeight.W_600)], tight=True),
        padding=pad(h=16, v=10),
        bgcolor="transparent",
        border_radius=10,
        on_click=lambda _: _trocar_aba(2),
    )

    seletor_abas = ft.Container(
        padding=pad(all_=4),
        bgcolor=T.SURFACE,
        border_radius=12,
        border=borda(),
        content=ft.Row(spacing=4, tight=True, controls=[btn_perfil, btn_categorias, btn_destinos]),
    )

    cabecalho = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            ft.Column(
                spacing=2,
                controls=[
                    ft.Row(spacing=8, controls=[
                        ft.Text("Configurações & Cadastros Base", color=T.TEXT_PRIMARY, size=22, weight=ft.FontWeight.BOLD),
                        spinner,
                    ]),
                    ft.Text("Gerencie dados do seu perfil, categorias orçamentárias e destinos", color=T.TEXT_MUTED, size=12),
                ],
            ),
        ],
    )

    conteudo = ft.Column(
        spacing=0,
        controls=[
            cabecalho,
            ft.Container(height=18),
            seletor_abas,
            ft.Container(height=18),
            area_conteudo,
            ft.Container(height=30),
        ],
    )

    renderizar_aba()

    return criar_shell(page, rota_ativa=ROTA_CONFIG, conteudo=conteudo)
