"""
=============================================================================
DemBase v3 — views/widgets/seletor_perfil.py (Flet 1.0.1)
Seletor global de Visão Familiar ("Eu, Ela & Nós") no cabeçalho.
Permite alternar entre perfis individuais (ex: Denilson, Erika) e a visão
consolidada da família (Casa / Todos), com recálculo reativo instantâneo.
=============================================================================
"""
from __future__ import annotations

from typing import Callable, Optional
import flet as ft

from core import theme as T
from core.theme import pad, borda, abrir_dialogo, fechar_dialogo, mostrar_feedback
from core.membro_state import (
    obter_visao_membro_atual,
    definir_visao_membro_atual,
)
import services.supabase_client as db

CORES_MEMBROS = [
    ("#6366F1", "Índigo"),
    ("#EC4899", "Rosa"),
    ("#10B981", "Esmeralda"),
    ("#F59E0B", "Âmbar"),
    ("#8B5CF6", "Roxo"),
    ("#06B6D4", "Ciano"),
    ("#EF4444", "Vermelho"),
    ("#3B82F6", "Azul"),
]


def criar_seletor_perfil(
    page: ft.Page,
    on_change: Optional[Callable[[str | None], None]] = None,
    is_mobile: bool = False,
) -> ft.Control:
    """
    Cria a pílula interativa do seletor de perfil para o cabeçalho.
    Desktop: [👤 Denilson ▾] ou [🏠 Casa (Todos) ▾]
    Mobile: Botão compacto com avatar/ícone colorido.
    """
    estado_vis = obter_visao_membro_atual(page)
    _trocando = False

    txt_nome = ft.Text(
        estado_vis["nome"],
        color=T.TEXT_PRIMARY,
        size=12 if is_mobile else 13.5,
        weight=ft.FontWeight.W_600,
        max_lines=1,
        overflow=ft.TextOverflow.ELLIPSIS,
    )

    icone_vis = ft.Icon(
        ft.Icons.HOME_ROUNDED if estado_vis["eh_casa"] else ft.Icons.PERSON_ROUNDED,
        color=estado_vis["cor"],
        size=14 if is_mobile else 16,
    )

    def _atualizar_rotulo():
        vis = obter_visao_membro_atual(page)
        txt_nome.value = vis["nome"]
        icone_vis.icon = ft.Icons.HOME_ROUNDED if vis["eh_casa"] else ft.Icons.PERSON_ROUNDED
        icone_vis.color = vis["cor"]
        try:
            txt_nome.update()
            icone_vis.update()
        except Exception:
            try:
                page.update()
            except Exception:
                pass

    page._shell_atualizar_rotulo_perfil = _atualizar_rotulo

    def _abrir_modal_perfis(_=None):
        nonlocal _trocando
        if _trocando:
            return

        dialog_perfis = None

        def _selecionar_perfil(membro_id: str | None, membro_info: dict | None = None):
            nonlocal _trocando
            if _trocando:
                return
            _trocando = True

            try:
                fechar_dialogo(page, dialog_perfis)
            except Exception:
                pass

            # Define a nova visão e executa a RPC no Supabase
            novo_est = definir_visao_membro_atual(page, membro_id, membro_info)
            _atualizar_rotulo()

            _trocando = False

            # Dispara callback para recalcular as métricas da tela atual
            if callable(on_change):
                try:
                    on_change(novo_est.get("membro_id"))
                except Exception as ex:
                    print(f"[SeletorPerfil] Erro no callback on_change: {ex}")

        # Modal de Adicionar Novo Membro
        def _abrir_modal_novo_membro(_=None):
            try:
                fechar_dialogo(page, dialog_perfis)
            except Exception:
                pass

            txt_novo_nome = ft.TextField(
                label="Nome do Perfil",
                hint_text="Ex: Esposa, Erika, Filho...",
                border_color=T.BORDER,
                focused_border_color=T.PRIMARY,
                text_size=14,
                autofocus=True,
            )

            cor_selecionada = ["#EC4899"]

            def _criar_chip_cor(hex_cor: str, nome_cor: str) -> ft.Container:
                def _escolher(_):
                    cor_selecionada[0] = hex_cor
                    for c_ctrl in row_cores.controls:
                        sel = (c_ctrl.data == hex_cor)
                        c_ctrl.border = borda(2.5, T.TEXT_PRIMARY if sel else "transparent")
                    page.update()

                return ft.Container(
                    data=hex_cor,
                    width=28,
                    height=28,
                    border_radius=14,
                    bgcolor=hex_cor,
                    border=borda(2.5, T.TEXT_PRIMARY if hex_cor == cor_selecionada[0] else "transparent"),
                    on_click=_escolher,
                    tooltip=nome_cor,
                    ink=True,
                )

            row_cores = ft.Row(
                spacing=8,
                wrap=True,
                controls=[_criar_chip_cor(c, n) for c, n in CORES_MEMBROS],
            )

            dialog_novo = None

            def _salvar_novo(_):
                nome_m = (txt_novo_nome.value or "").strip()
                if not nome_m:
                    mostrar_feedback(page, "Digite um nome para o perfil.", "alerta")
                    return
                try:
                    novo = db.criar_membro({
                        "nome": nome_m,
                        "cor": cor_selecionada[0],
                        "icone": "person",
                        "principal": False,
                    })
                    fechar_dialogo(page, dialog_novo)
                    mostrar_feedback(page, f"Perfil '{nome_m}' criado!", "sucesso")
                    # Seleciona o novo perfil imediatamente
                    _selecionar_perfil(novo.get("id"), novo)
                except Exception as ex:
                    mostrar_feedback(page, f"Erro ao criar perfil: {ex}", "erro")

            dialog_novo = ft.AlertDialog(
                title=ft.Text("Novo Perfil Familiar", size=17, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY),
                content=ft.Container(
                    width=380,
                    content=ft.Column(
                        tight=True,
                        spacing=16,
                        controls=[
                            txt_novo_nome,
                            ft.Text("Cor de identificação:", size=12, color=T.TEXT_MUTED, weight=ft.FontWeight.W_500),
                            row_cores,
                        ],
                    ),
                ),
                actions=[
                    ft.TextButton("Cancelar", on_click=lambda _: fechar_dialogo(page, dialog_novo)),
                    ft.FilledButton("Criar Perfil", on_click=_salvar_novo, style=ft.ButtonStyle(bgcolor=T.PRIMARY)),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
            abrir_dialogo(page, dialog_novo)

        # Monta a lista de opções de perfis
        membros = db.listar_membros()
        vis_atual = obter_visao_membro_atual(page)

        def _item_opcao(
            titulo: str,
            subtitulo: str,
            icone: str,
            cor: str,
            selecionado: bool,
            on_click_fn,
            badge_txt: Optional[str] = None,
        ) -> ft.Container:
            return ft.Container(
                padding=pad(h=14, v=10),
                border_radius=10,
                bgcolor=f"{cor}14" if selecionado else T.SURFACE_ALT,
                border=borda(1.5 if selecionado else 1, cor if selecionado else T.BORDER),
                on_click=on_click_fn,
                ink=True,
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Row(
                            spacing=12,
                            tight=True,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Container(
                                    width=34,
                                    height=34,
                                    border_radius=17,
                                    bgcolor=f"{cor}24",
                                    alignment=ft.Alignment(0, 0),
                                    content=ft.Icon(icone, color=cor, size=18),
                                ),
                                ft.Column(
                                    spacing=2,
                                    tight=True,
                                    controls=[
                                        ft.Row(
                                            spacing=6,
                                            tight=True,
                                            controls=[
                                                ft.Text(titulo, size=13.5, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY),
                                                *(
                                                    [
                                                        ft.Container(
                                                            padding=pad(h=6, v=1.5),
                                                            bgcolor=f"{cor}20",
                                                            border_radius=6,
                                                            content=ft.Text(badge_txt, size=10, color=cor, weight=ft.FontWeight.BOLD),
                                                        )
                                                    ]
                                                    if badge_txt
                                                    else []
                                                ),
                                            ],
                                        ),
                                        ft.Text(subtitulo, size=11, color=T.TEXT_MUTED),
                                    ],
                                ),
                            ],
                        ),
                        ft.Icon(
                            ft.Icons.CHECK_CIRCLE_ROUNDED if selecionado else ft.Icons.RADIO_BUTTON_UNCHECKED_ROUNDED,
                            color=cor if selecionado else T.TEXT_MUTED,
                            size=18,
                        ),
                    ],
                ),
            )

        controles_modal = [
            ft.Text("Visão de Visualização", size=16, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY),
            ft.Text(
                "Alterne entre a visão consolidada da casa e perfis individuais.",
                size=12,
                color=T.TEXT_MUTED,
            ),
            ft.Container(height=4),
            # Opção 1: Casa / Todos
            _item_opcao(
                titulo="Casa / Todos (Familiar)",
                subtitulo="Soma consolidada de todos os membros",
                icone=ft.Icons.HOME_ROUNDED,
                cor="#818CF8",
                selecionado=vis_atual["eh_casa"],
                on_click_fn=lambda _: _selecionar_perfil(None),
                badge_txt="Consolidado",
            ),
            ft.Divider(color=T.BORDER, height=14),
            ft.Text("Perfis Familiares:", size=11.5, weight=ft.FontWeight.W_600, color=T.TEXT_MUTED),
        ]

        # Membros cadastrados
        for m in membros:
            m_id = str(m["id"])
            m_nome = m.get("nome", "Membro")
            m_cor = m.get("cor") or "#6366F1"
            m_prin = bool(m.get("principal"))
            sel = (not vis_atual["eh_casa"] and vis_atual["membro_id"] == m_id)

            controles_modal.append(
                _item_opcao(
                    titulo=m_nome,
                    subtitulo="Contas, cartões e despesas deste perfil",
                    icone=ft.Icons.PERSON_ROUNDED,
                    cor=m_cor,
                    selecionado=sel,
                    on_click_fn=lambda _, mid=m_id, minf=m: _selecionar_perfil(mid, minf),
                    badge_txt="Principal" if m_prin else None,
                )
            )

        # Botão para adicionar novo membro
        controles_modal.append(ft.Container(height=6))
        controles_modal.append(
            ft.OutlinedButton(
                content=ft.Row(
                    spacing=6,
                    alignment=ft.MainAxisAlignment.CENTER,
                    controls=[
                        ft.Icon(ft.Icons.PERSON_ADD_ROUNDED, size=15, color=T.PRIMARY),
                        ft.Text("Adicionar Membro Familiar", size=12.5, color=T.PRIMARY, weight=ft.FontWeight.W_600),
                    ],
                ),
                style=ft.ButtonStyle(
                    side=ft.BorderSide(1, T.PRIMARY),
                    shape=ft.RoundedRectangleBorder(radius=8),
                    padding=pad(h=12, v=10),
                ),
                on_click=_abrir_modal_novo_membro,
            )
        )

        dialog_perfis = ft.AlertDialog(
            content=ft.Container(
                width=380,
                content=ft.Column(
                    tight=True,
                    spacing=8,
                    scroll=ft.ScrollMode.AUTO,
                    controls=controles_modal,
                ),
            ),
            actions=[
                ft.TextButton("Fechar", on_click=lambda _: fechar_dialogo(page, dialog_perfis)),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        abrir_dialogo(page, dialog_perfis)

    # Botão visual do seletor
    if is_mobile:
        return ft.Container(
            content=ft.Row(
                spacing=4,
                tight=True,
                controls=[
                    icone_vis,
                    txt_nome,
                    ft.Icon(ft.Icons.KEYBOARD_ARROW_DOWN_ROUNDED, color=T.TEXT_MUTED, size=14),
                ],
            ),
            padding=pad(h=8, v=5),
            bgcolor=T.SURFACE_ALT,
            border_radius=18,
            border=borda(1, f"{estado_vis['cor']}50"),
            on_click=_abrir_modal_perfis,
            ink=True,
            tooltip="Alternar perfil familiar",
        )

    # Layout Desktop: pílula elegante padronizada com o seletor de mês
    return ft.Container(
        content=ft.Row(
            spacing=6,
            tight=True,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                icone_vis,
                txt_nome,
                ft.Icon(ft.Icons.KEYBOARD_ARROW_DOWN_ROUNDED, color=T.TEXT_MUTED, size=15),
            ],
        ),
        padding=pad(h=12, v=6),
        bgcolor=T.SURFACE_ALT,
        border_radius=20,
        border=borda(1, f"{estado_vis['cor']}40"),
        on_click=_abrir_modal_perfis,
        ink=True,
        tooltip="Alternar entre Eu, Ela ou Casa (Consolidado)",
    )
