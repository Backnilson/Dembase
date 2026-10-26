"""
=============================================================================
DemBase v3 — views/config_view.py  (Flet 1.0.1)
Configurações do Usuário e Cadastros Base:
- Meu Perfil
- Metas (6 Potes)
- Caixinhas de Teto (embutido inline igual Metas)
- Categorias & Subcategorias (embutido inline igual Metas)
- Aparência & Tema
- Gráficos do Dashboard
- Destinos
Montado DENTRO do Shell (sidebar + header).
=============================================================================
"""
from __future__ import annotations

import flet as ft
from core import theme as T
from core.theme import pad, borda, mostrar_feedback, abrir_dialogo, fechar_dialogo
from core.router import ROTA_CONFIG, ROTA_AUTH, navegar
from core import storage
from views.shell_view import criar_shell
from views.widgets.potes_config import montar_aba_potes
from views.caixinhas_view import montar_aba_caixinhas
from views.categorias_view import montar_aba_categorias
import services.supabase_client as db

DESTINOS_PADRAO = ["Eu", "Casa", "Moto", "Carro", "DJ", "Família", "Outros"]


def criar_view_config(page: ft.Page, match=None) -> ft.View:
    # 0: Perfil, 1: Metas (Potes), 2: Caixinhas, 3: Categorias, 4: Tema, 5: Gráficos, 6: Destinos
    aba_inicial = 0
    aba_query = ""
    if match and getattr(match, "query", None):
        aba_query = str(match.query.get("aba") or "").strip().lower()
    elif "?" in str(getattr(page, "route", "")):
        try:
            q_part = str(page.route).split("?", 1)[1]
            for kv in q_part.split("&"):
                if kv.startswith("aba="):
                    aba_query = kv.split("=", 1)[1].strip().lower()
        except Exception:
            pass

    if aba_query in ("metas", "potes"):
        aba_inicial = 1
    elif aba_query in ("caixinhas", "caixinha"):
        aba_inicial = 2
    elif aba_query in ("categorias", "categoria"):
        aba_inicial = 3
    elif aba_query in ("tema", "aparencia"):
        aba_inicial = 4
    elif aba_query in ("graficos", "dashboard"):
        aba_inicial = 5
    elif aba_query in ("destinos", "destino"):
        aba_inicial = 6

    aba_ativa = [aba_inicial]
    spinner = ft.ProgressRing(color=T.PRIMARY, width=20, height=20, stroke_width=2, visible=False)

    area_conteudo = ft.Column(spacing=16, controls=[])

    # ── 0. ABA PERFIL ────────────────────────────────────────────────────────
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

        async def sair_app(_):
            try:
                await storage.limpar_sessao_autenticada(page)
                await storage.salvar_ultima_rota(page, ROTA_AUTH)
                db.fazer_logout()
            except Exception:
                pass
            from core.window_manager import ajustar_janela_login
            await ajustar_janela_login(page)
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

    # ── 6. ABA DESTINOS ──────────────────────────────────────────────────────
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
                    fechar_dialogo(page, modal_dest)
                    mostrar_feedback(page, "Destino criado com sucesso!", "sucesso")
                    carregar_destinos()
                except Exception as ex:
                    mostrar_feedback(page, f"Erro ao criar destino: {ex}", "erro")

            modal_dest = ft.AlertDialog(
                title=ft.Text("Novo Destino", color=T.TEXT_PRIMARY, size=18, weight=ft.FontWeight.BOLD),
                content=ft.Column(spacing=12, tight=True, controls=[txt_nome_dest]),
                actions=[
                    ft.TextButton(content=ft.Text("Cancelar", color=T.TEXT_MUTED), on_click=lambda _: fechar_dialogo(page, modal_dest)),
                    ft.FilledButton(content=ft.Text("Salvar"), style=ft.ButtonStyle(bgcolor=T.PRIMARY), on_click=salvar_dest),
                ],
            )
            abrir_dialogo(page, modal_dest)

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

    # ── 4. ABA APARÊNCIA & TEMA ──────────────────────────────────────────────
    def _montar_aba_tema():
        pref_atual = storage.obter_preferencia_tema_memoria(page) or "system"

        def _card_opcao_tema(chave: str, titulo: str, subtitulo: str, icone, badge_texto: str):
            ativo = (pref_atual == chave)
            cor_destaque = T.NEON if T.IS_DARK else T.PRIMARY

            async def _selecionar(_):
                await storage.salvar_preferencia_tema(page, chave)
                T.aplicar_tema_app(page, chave)
                mostrar_feedback(page, f"Tema configurado para: {titulo}!", "sucesso")

            return ft.Container(
                expand=True,
                padding=pad(all_=18),
                bgcolor=T.SURFACE_ALT if not ativo else (f"{cor_destaque}14"),
                border_radius=14,
                border=borda(width=2 if ativo else 1, color=cor_destaque if ativo else T.BORDER),
                on_click=_selecionar,
                content=ft.Column(
                    spacing=10,
                    controls=[
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.Container(
                                    width=40, height=40,
                                    bgcolor=f"{cor_destaque}22" if ativo else f"{T.BORDER}44",
                                    border_radius=10,
                                    alignment=ft.Alignment(0, 0),
                                    content=ft.Icon(icone, color=cor_destaque if ativo else T.TEXT_PRIMARY, size=20),
                                ),
                                ft.Icon(
                                    ft.Icons.CHECK_CIRCLE_ROUNDED if ativo else ft.Icons.RADIO_BUTTON_UNCHECKED_ROUNDED,
                                    color=cor_destaque if ativo else T.TEXT_MUTED,
                                    size=20,
                                ),
                            ],
                        ),
                        ft.Column(
                            spacing=3,
                            controls=[
                                ft.Text(titulo, size=14, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY),
                                ft.Text(subtitulo, size=12, color=T.TEXT_MUTED, height=1.3),
                            ],
                        ),
                        ft.Container(
                            padding=pad(h=8, v=3),
                            bgcolor=f"{cor_destaque}20" if ativo else f"{T.BORDER}33",
                            border_radius=6,
                            content=ft.Text(badge_texto, size=11, color=cor_destaque if ativo else T.TEXT_MUTED, weight=ft.FontWeight.W_600),
                        ),
                    ],
                ),
            )

        card_sistema = _card_opcao_tema(
            "system",
            "Acompanhar Sistema",
            "Acompanha o modo Claro ou Escuro do seu celular/PC em tempo real.",
            ft.Icons.BRIGHTNESS_AUTO_ROUNDED,
            "Padrão Automático (ThemeMode.system)",
        )
        card_escuro = _card_opcao_tema(
            "dark",
            "Modo Escuro",
            "Fundo preto suave com detalhes em Verde Neon de alto contraste.",
            ft.Icons.DARK_MODE_ROUNDED,
            "Forçar Escuro Permanente",
        )
        card_claro = _card_opcao_tema(
            "light",
            "Modo Claro",
            "Fundo claro com tipografia nítida e contraste otimizado.",
            ft.Icons.LIGHT_MODE_ROUNDED,
            "Forçar Claro Permanente",
        )

        status_texto = (
            "Seguindo o sistema do dispositivo em tempo real" if pref_atual == "system"
            else ("Modo Escuro permanente selecionado" if pref_atual == "dark" else "Modo Claro permanente selecionado")
        )

        return ft.Container(
            padding=pad(all_=24),
            bgcolor=T.SURFACE,
            border_radius=16,
            border=borda(),
            content=ft.Column(
                spacing=20,
                controls=[
                    ft.Row(
                        spacing=12,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Container(
                                width=40, height=40,
                                bgcolor=f"{T.NEON}20" if T.IS_DARK else f"{T.PRIMARY}20",
                                border_radius=10,
                                alignment=ft.Alignment(0, 0),
                                content=ft.Icon(ft.Icons.PALETTE_OUTLINED, color=T.NEON if T.IS_DARK else T.PRIMARY, size=22),
                            ),
                            ft.Column(
                                spacing=2,
                                controls=[
                                    ft.Text("Aparência & Preferência de Tema", color=T.TEXT_PRIMARY, size=16, weight=ft.FontWeight.BOLD),
                                    ft.Text(f"Preferência ativa: {status_texto}", color=T.TEXT_MUTED, size=12),
                                ],
                            ),
                        ],
                    ),
                    ft.Divider(color=T.BORDER, height=1),
                    ft.ResponsiveRow(
                        spacing=14,
                        run_spacing=14,
                        controls=[
                            ft.Container(col={"xs": 12, "md": 4}, content=card_sistema),
                            ft.Container(col={"xs": 12, "md": 4}, content=card_escuro),
                            ft.Container(col={"xs": 12, "md": 4}, content=card_claro),
                        ],
                    ),
                ],
            ),
        )

    # ── 5. ABA GRÁFICOS DO DASHBOARD ─────────────────────────────────────────
    def _montar_aba_graficos():
        from views.widgets.dashboard_charts import DASHBOARD_CHARTS_CATALOG, GRAFICOS_PADRAO_IDS

        ativos = set(storage.obter_graficos_dashboard_memoria(page, GRAFICOS_PADRAO_IDS))
        switches: dict[str, ft.Switch] = {}

        def _ao_alternar(_):
            selecionados = [
                item["id"]
                for item in DASHBOARD_CHARTS_CATALOG
                if switches[item["id"]].value
            ]
            if not selecionados:
                mostrar_feedback(page, "Mantenha ao menos 1 gráfico ativo no Dashboard.", "alerta")
                return
            storage.salvar_graficos_dashboard_sync(page, selecionados)
            mostrar_feedback(page, "Preferências de gráficos do Dashboard salvas!", "sucesso")

        linhas_graf = []
        for item in DASHBOARD_CHARTS_CATALOG:
            cid = item["id"]
            sw = ft.Switch(
                value=(cid in ativos),
                active_color=T.PRIMARY,
                on_change=_ao_alternar,
            )
            switches[cid] = sw
            linhas_graf.append(
                ft.Container(
                    padding=pad(h=14, v=12),
                    bgcolor=T.SURFACE_ALT,
                    border_radius=12,
                    border=borda(),
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Row(
                                spacing=12,
                                expand=True,
                                controls=[
                                    ft.Container(
                                        padding=pad(all_=8),
                                        bgcolor=f"{item['cor']}1F",
                                        border_radius=10,
                                        content=ft.Icon(item["icone"], color=item["cor"], size=20),
                                    ),
                                    ft.Column(
                                        spacing=2,
                                        expand=True,
                                        controls=[
                                            ft.Text(item["titulo"].strip(), color=T.TEXT_PRIMARY, size=14, weight=ft.FontWeight.BOLD),
                                            ft.Text(item["subtitulo"], color=T.TEXT_MUTED, size=12),
                                        ],
                                    ),
                                ],
                            ),
                            sw,
                        ],
                    ),
                )
            )

        return ft.Container(
            padding=pad(all_=24),
            bgcolor=T.SURFACE,
            border_radius=16,
            border=borda(),
            content=ft.Column(
                spacing=14,
                controls=[
                    ft.Row(
                        spacing=10,
                        controls=[
                            ft.Icon(ft.Icons.DASHBOARD_CUSTOMIZE_ROUNDED, color=T.PRIMARY, size=24),
                            ft.Column(
                                spacing=2,
                                controls=[
                                    ft.Text("Gráficos da Tela Inicial (Dashboard)", color=T.TEXT_PRIMARY, size=17, weight=ft.FontWeight.BOLD),
                                    ft.Text("Escolha quais análises visuais devem aparecer na sua tela inicial.", color=T.TEXT_MUTED, size=12),
                                ],
                            ),
                        ],
                    ),
                    ft.Divider(height=1, color=T.BORDER),
                    *linhas_graf,
                ],
            ),
        )

    # ── Alternar Abas ────────────────────────────────────────────────────────
    botoes_abas_lista: list[tuple[int, ft.Container]] = []

    def renderizar_aba():
        area_conteudo.controls.clear()
        idx = aba_ativa[0]
        if idx == 0:
            area_conteudo.controls.append(_montar_aba_perfil())
        elif idx == 1:
            area_conteudo.controls.append(montar_aba_potes(page))
        elif idx == 2:
            area_conteudo.controls.append(montar_aba_caixinhas(page))
        elif idx == 3:
            area_conteudo.controls.append(montar_aba_categorias(page))
        elif idx == 4:
            area_conteudo.controls.append(_montar_aba_tema())
        elif idx == 5:
            area_conteudo.controls.append(_montar_aba_graficos())
        else:
            area_conteudo.controls.append(_montar_aba_destinos())
        try:
            page.update()
        except Exception:
            pass

    def _trocar_aba(idx: int):
        aba_ativa[0] = idx
        for i_b, btn_c in botoes_abas_lista:
            btn_c.bgcolor = f"{T.PRIMARY}18" if i_b == idx else "transparent"
        renderizar_aba()

    definicao_abas = [
        (0, "Meu Perfil",        ft.Icons.PERSON_OUTLINED),
        (1, "Metas (Potes)",     ft.Icons.DONUT_LARGE_ROUNDED),
        (2, "Caixinhas",         ft.Icons.INVENTORY_2_ROUNDED),
        (3, "Categorias",        ft.Icons.CATEGORY_OUTLINED),
        (4, "Aparência & Tema",  ft.Icons.PALETTE_OUTLINED),
        (5, "Gráficos",          ft.Icons.DASHBOARD_CUSTOMIZE_ROUNDED),
        (6, "Destinos",          ft.Icons.LOCATION_ON_OUTLINED),
    ]

    controles_abas: list[ft.Control] = []
    for idx_a, rotulo_a, icone_a in definicao_abas:
        btn = ft.Container(
            content=ft.Row(
                [ft.Icon(icone_a, size=16), ft.Text(rotulo_a, size=13, weight=ft.FontWeight.W_600)],
                tight=True,
                spacing=6,
            ),
            padding=pad(h=14, v=10),
            bgcolor=f"{T.PRIMARY}18" if aba_inicial == idx_a else "transparent",
            border_radius=10,
            ink=True,
            on_click=lambda _, i=idx_a: _trocar_aba(i),
        )
        botoes_abas_lista.append((idx_a, btn))
        controles_abas.append(btn)

    seletor_abas = ft.Container(
        padding=pad(all_=4),
        bgcolor=T.SURFACE,
        border_radius=12,
        border=borda(),
        content=ft.Row(
            spacing=4,
            tight=True,
            scroll=ft.ScrollMode.ADAPTIVE,
            controls=controles_abas,
        ),
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
                    ft.Text("Gerencie seu perfil, metas dos 6 potes, caixinhas de teto, categorias e aparência", color=T.TEXT_MUTED, size=12),
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
