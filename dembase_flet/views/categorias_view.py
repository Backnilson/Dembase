"""
=============================================================================
DemBase v3 — views/categorias_view.py  (Flet 1.0.1)
Módulo exclusivo e completo para administração de Categorias e Subcategorias.
Acessado diretamente pelo menu lateral (Sidebar).
Permite criar, renomear, listar e excluir categorias e suas subcategorias filhas.
=============================================================================
"""
import flet as ft
from core import theme as T
from core.theme import pad, borda, mostrar_feedback
from core.router import ROTA_CATEGORIAS
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


def criar_view_categorias(page: ft.Page) -> ft.View:
    col_categorias = ft.Column(spacing=12)
    spinner = ft.ProgressRing(color=T.PRIMARY, width=20, height=20, stroke_width=2, visible=False)
    txt_busca = ft.TextField(
        hint_text="Buscar categoria ou subcategoria...",
        prefix_icon=ft.Icons.SEARCH_ROUNDED,
        **T.campo_estilo(),
    )

    def carregar_dados():
        col_categorias.controls.clear()
        spinner.visible = True
        page.update()

        try:
            categorias = db.listar_categorias()
            todas_subcats = db.listar_subcategorias()

            termo = txt_busca.value.strip().lower() if txt_busca.value else ""

            if not categorias:
                col_categorias.controls.append(
                    ft.Container(
                        padding=pad(all_=40),
                        alignment=ft.Alignment(0, 0),
                        content=ft.Column(
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=12,
                            controls=[
                                ft.Icon(ft.Icons.CATEGORY_OUTLINED, size=52, color=T.TEXT_MUTED),
                                ft.Text("Nenhuma categoria encontrada", color=T.TEXT_PRIMARY, size=16, weight=ft.FontWeight.BOLD),
                                ft.Text("Comece criando uma nova categoria ou carregue o pacote padrão do DemBase.", color=T.TEXT_MUTED, size=13),
                                ft.Row(
                                    alignment=ft.MainAxisAlignment.CENTER,
                                    spacing=10,
                                    controls=[
                                        ft.FilledButton(
                                            content=ft.Text("⚡ Carregar Categorias Padrão"),
                                            style=ft.ButtonStyle(bgcolor=T.PRIMARY),
                                            on_click=carregar_padrao,
                                        ),
                                        ft.OutlinedButton(
                                            content=ft.Text("+ Nova Categoria"),
                                            on_click=lambda _: abrir_modal_categoria(),
                                        ),
                                    ],
                                ),
                            ],
                        ),
                    )
                )
                spinner.visible = False
                page.update()
                return

            for cat in categorias:
                cat_id = str(cat["id"])
                cat_nome = cat.get("nome", "Sem Nome")
                cat_cor = cat.get("cor") or T.PRIMARY

                # Filtra subcategorias pertencentes a esta categoria
                subcats_cat = [s for s in todas_subcats if str(s.get("categoria_id")) == cat_id]

                # Se houver termo de busca, filtra
                if termo:
                    nome_bate = termo in cat_nome.lower()
                    subcat_bate = any(termo in s.get("nome", "").lower() for s in subcats_cat)
                    if not nome_bate and not subcat_bate:
                        continue

                # Lista de chips/linhas de subcategorias
                chips_subcats = ft.Row(wrap=True, spacing=8, run_spacing=8)

                if subcats_cat:
                    for sub in subcats_cat:
                        sub_id = str(sub["id"])
                        sub_nome = sub.get("nome", "")

                        def _excluir_sub(s_id=sub_id, s_nome=sub_nome):
                            try:
                                db.deletar_subcategoria(s_id)
                                mostrar_feedback(page, f"Subcategoria '{s_nome}' inativada!", "sucesso")
                                carregar_dados()
                            except Exception as ex:
                                mostrar_feedback(page, f"Erro: {ex}", "erro")

                        def _editar_sub(s_id=sub_id, s_nome=sub_nome, c_id=cat_id, c_nome=cat_nome):
                            abrir_modal_subcategoria(c_id, c_nome, sub_id_edicao=s_id, nome_atual=s_nome)

                        chip = ft.Container(
                            padding=pad(h=10, v=6),
                            bgcolor=T.SURFACE_ALT,
                            border_radius=8,
                            border=borda(),
                            content=ft.Row(
                                spacing=6,
                                tight=True,
                                controls=[
                                    ft.Icon(ft.Icons.SUBDIRECTORY_ARROW_RIGHT_ROUNDED, size=14, color=T.PRIMARY),
                                    ft.Text(sub_nome, color=T.TEXT_PRIMARY, size=12, weight=ft.FontWeight.W_500),
                                    ft.IconButton(
                                        icon=ft.Icons.EDIT_ROUNDED,
                                        icon_size=13,
                                        icon_color=T.TEXT_MUTED,
                                        tooltip="Renomear",
                                        on_click=lambda _, sid=sub_id, snome=sub_nome: _editar_sub(sid, snome),
                                    ),
                                    ft.IconButton(
                                        icon=ft.Icons.CLOSE_ROUNDED,
                                        icon_size=13,
                                        icon_color=T.DESPESA,
                                        tooltip="Excluir",
                                        on_click=lambda _, sid=sub_id: _excluir_sub(sid),
                                    ),
                                ],
                            ),
                        )
                        chips_subcats.controls.append(chip)
                else:
                    chips_subcats.controls.append(
                        ft.Text("Nenhuma subcategoria cadastrada ainda.", color=T.TEXT_MUTED, size=12, italic=True)
                    )

                def _excluir_cat(c_id=cat_id, c_nome=cat_nome):
                    try:
                        db.deletar_categoria(c_id)
                        mostrar_feedback(page, f"Categoria '{c_nome}' inativada!", "sucesso")
                        carregar_dados()
                    except Exception as ex:
                        mostrar_feedback(page, f"Erro ao excluir categoria: {ex}", "erro")

                def _editar_cat(c_id=cat_id, c_nome=cat_nome):
                    abrir_modal_categoria(cat_id_edicao=c_id, nome_atual=c_nome)

                def _adicionar_sub_para_cat(c_id=cat_id, c_nome=cat_nome):
                    abrir_modal_subcategoria(c_id, c_nome)

                card_categoria = ft.Container(
                    padding=pad(all_=16),
                    bgcolor=T.SURFACE,
                    border_radius=14,
                    border=borda(),
                    content=ft.Column(
                        spacing=12,
                        controls=[
                            # Cabeçalho da Categoria
                            ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    ft.Row(
                                        spacing=10,
                                        controls=[
                                            ft.Container(width=14, height=14, bgcolor=cat_cor, border_radius=7),
                                            ft.Text(cat_nome, color=T.TEXT_PRIMARY, size=16, weight=ft.FontWeight.BOLD),
                                            ft.Container(
                                                content=ft.Text("Universal", size=10, color=T.PRIMARY, weight=ft.FontWeight.W_600),
                                                bgcolor=f"{T.PRIMARY}18",
                                                padding=pad(h=8, v=2),
                                                border_radius=6,
                                            ),
                                        ],
                                    ),
                                    ft.Row(
                                        spacing=4,
                                        controls=[
                                            ft.TextButton(
                                                content=ft.Row([ft.Icon(ft.Icons.ADD_ROUNDED, size=16), ft.Text("Subcategoria", size=12)]),
                                                on_click=lambda _, cid=cat_id, cnome=cat_nome: _adicionar_sub_para_cat(cid, cnome),
                                            ),
                                            ft.IconButton(
                                                icon=ft.Icons.EDIT_ROUNDED,
                                                icon_size=18,
                                                icon_color=T.TEXT_MUTED,
                                                tooltip="Renomear Categoria",
                                                on_click=lambda _, cid=cat_id, cnome=cat_nome: _editar_cat(cid, cnome),
                                            ),
                                            ft.IconButton(
                                                icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                                                icon_size=18,
                                                icon_color=T.DESPESA,
                                                tooltip="Inativar Categoria",
                                                on_click=lambda _, cid=cat_id, cnome=cat_nome: _excluir_cat(cid, cnome),
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                            # Lista de Subcategorias filhas
                            ft.Divider(color=T.BORDER, height=1),
                            ft.Text("Subcategorias vinculadas:", color=T.TEXT_MUTED, size=11, weight=ft.FontWeight.W_600),
                            chips_subcats,
                        ],
                    ),
                )
                col_categorias.controls.append(card_categoria)

        except Exception as ex:
            mostrar_feedback(page, f"Erro ao listar dados: {ex}", "erro")
        finally:
            spinner.visible = False
            page.update()

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
        mostrar_feedback(page, f"{inseridos} categorias padrão carregadas!", "sucesso")
        carregar_dados()

    # ---- Modal de Categoria (Criar / Editar) ----
    def abrir_modal_categoria(cat_id_edicao: str = None, nome_atual: str = ""):
        txt_nome = ft.TextField(
            label="Nome da Categoria *",
            value=nome_atual,
            hint_text="Ex: Alimentação, DJ, Investimentos",
            autofocus=True,
            **T.campo_estilo(),
        )

        def salvar(_):
            nome = txt_nome.value.strip()
            if not nome:
                mostrar_feedback(page, "Informe o nome da categoria.", "alerta")
                return
            try:
                if cat_id_edicao:
                    db.atualizar_categoria(cat_id_edicao, {"nome": nome})
                    mostrar_feedback(page, "Categoria atualizada com sucesso!", "sucesso")
                else:
                    db.criar_categoria({"nome": nome, "tipo": "ambos", "cor": T.PRIMARY, "icone": "category"})
                    mostrar_feedback(page, "Categoria criada com sucesso!", "sucesso")
                modal.open = False
                page.update()
                carregar_dados()
            except Exception as ex:
                mostrar_feedback(page, f"Erro ao salvar: {ex}", "erro")

        modal = ft.AlertDialog(
            title=ft.Row([
                ft.Icon(ft.Icons.CATEGORY_ROUNDED, color=T.PRIMARY, size=22),
                ft.Text("Editar Categoria" if cat_id_edicao else "Nova Categoria Universal", size=18, weight=ft.FontWeight.BOLD),
            ], spacing=8),
            content=ft.Column(spacing=12, tight=True, controls=[
                ft.Text("Categorias universais atendem tanto Receitas quanto Despesas.", color=T.TEXT_MUTED, size=12),
                txt_nome,
            ]),
            actions=[
                ft.TextButton(
                    content=ft.Text("Cancelar", color=T.TEXT_MUTED),
                    on_click=lambda _: (setattr(modal, "open", False), page.update()),
                ),
                ft.FilledButton(
                    content=ft.Text("Salvar"),
                    style=ft.ButtonStyle(bgcolor=T.PRIMARY),
                    on_click=salvar,
                ),
            ],
        )
        page.overlay.append(modal)
        modal.open = True
        page.update()

    # ---- Modal de Subcategoria (Criar / Editar) ----
    def abrir_modal_subcategoria(categoria_id: str, categoria_nome: str, sub_id_edicao: str = None, nome_atual: str = ""):
        txt_nome = ft.TextField(
            label="Nome da Subcategoria *",
            value=nome_atual,
            hint_text="Ex: Notebook, Supermercado, Combustível",
            autofocus=True,
            **T.campo_estilo(),
        )

        def salvar(_):
            nome = txt_nome.value.strip()
            if not nome:
                mostrar_feedback(page, "Informe o nome da subcategoria.", "alerta")
                return
            try:
                if sub_id_edicao:
                    db.atualizar_subcategoria(sub_id_edicao, {"nome": nome})
                    mostrar_feedback(page, "Subcategoria atualizada com sucesso!", "sucesso")
                else:
                    db.criar_subcategoria(categoria_id=categoria_id, nome=nome)
                    mostrar_feedback(page, f"Subcategoria vinculada a '{categoria_nome}' criada com sucesso!", "sucesso")
                modal_sub.open = False
                page.update()
                carregar_dados()
            except Exception as ex:
                mostrar_feedback(page, f"Erro ao salvar: {ex}", "erro")

        modal_sub = ft.AlertDialog(
            title=ft.Row([
                ft.Icon(ft.Icons.SUBDIRECTORY_ARROW_RIGHT_ROUNDED, color=T.PRIMARY, size=22),
                ft.Text("Editar Subcategoria" if sub_id_edicao else "Nova Subcategoria", size=18, weight=ft.FontWeight.BOLD),
            ], spacing=8),
            content=ft.Column(spacing=12, tight=True, controls=[
                ft.Container(
                    content=ft.Row([
                        ft.Text("Categoria Pai:", color=T.TEXT_MUTED, size=12),
                        ft.Text(categoria_nome, color=T.PRIMARY, size=13, weight=ft.FontWeight.BOLD),
                    ], spacing=6),
                    padding=pad(h=12, v=8),
                    bgcolor=T.SURFACE_ALT,
                    border_radius=8,
                    border=borda(),
                ),
                txt_nome,
            ]),
            actions=[
                ft.TextButton(
                    content=ft.Text("Cancelar", color=T.TEXT_MUTED),
                    on_click=lambda _: (setattr(modal_sub, "open", False), page.update()),
                ),
                ft.FilledButton(
                    content=ft.Text("Salvar"),
                    style=ft.ButtonStyle(bgcolor=T.PRIMARY),
                    on_click=salvar,
                ),
            ],
        )
        page.overlay.append(modal_sub)
        modal_sub.open = True
        page.update()

    txt_busca.on_change = lambda _: carregar_dados()

    # ---- Layout Geral ----
    cabecalho = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            ft.Column(spacing=2, controls=[
                ft.Row(spacing=8, controls=[
                    ft.Text("Categorias & Subcategorias", color=T.TEXT_PRIMARY, size=22, weight=ft.FontWeight.BOLD),
                    spinner,
                ]),
                ft.Text("Gerencie sua árvore de classificação para filtros e relatórios detalhados", color=T.TEXT_MUTED, size=12),
            ]),
            ft.Row(spacing=8, controls=[
                ft.OutlinedButton(
                    content=ft.Text("Carregar Padrão"),
                    on_click=carregar_padrao,
                ),
                ft.FilledButton(
                    content=ft.Row([ft.Icon(ft.Icons.ADD_ROUNDED, size=16), ft.Text("Nova Categoria")]),
                    style=ft.ButtonStyle(bgcolor=T.PRIMARY),
                    on_click=lambda _: abrir_modal_categoria(),
                ),
            ]),
        ],
    )

    conteudo = ft.Column(
        spacing=16,
        controls=[
            cabecalho,
            txt_busca,
            col_categorias,
            ft.Container(height=30),
        ],
    )

    carregar_dados()

    return criar_shell(page, rota_ativa=ROTA_CATEGORIAS, conteudo=conteudo)
