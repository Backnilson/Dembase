"""
DemBox Fatura — UI (Flet 1.0.1). Sem cálculo: tudo vem de core/dembox_fatura.py.
Sem SQL: toda persistência via services/supabase_client.py.

Seção plugada em views/caixinhas_view.py: banner de sugestão + cards de fatura.
Ações: Aportar, Retirar, Mover p/ outro Box, Pagar Fatura.
Cliques já são protegidos globalmente por core/click_guard.py; cada confirmação
ainda usa trava local (_em_andamento) e desabilita o botão durante a operação.
"""
from __future__ import annotations

from datetime import date
from typing import Callable

import flet as ft

from core import theme as T
from core import dembox_fatura as DF
from core.theme import pad, borda, mostrar_feedback, abrir_dialogo, fechar_dialogo
from core.constants import formatar_moeda
import services.supabase_client as db

COR_STATUS = {
    DF.STATUS_COBERTO: "#10B981",
    DF.STATUS_PARCIAL: "#F59E0B",
    DF.STATUS_RISCO: "#EF4444",
    DF.STATUS_AGUARDANDO: "#94A3B8",
    DF.STATUS_NEUTRO: "#94A3B8",
}


def _fmt_data(d: date | None) -> str:
    return d.strftime("%d/%m/%Y") if d else "—"


def _texto_dias(sit: DF.SituacaoBox) -> str:
    if sit.dias_ate_vencimento is None:
        return ""
    n = sit.dias_ate_vencimento
    if n < 0:
        return f"Venceu há {-n} dia(s)"
    if n == 0:
        return "Vence hoje"
    return f"Vence em {n} dia(s)"


def montar_secao_fatura(page: ft.Page, ao_mudar: Callable[[], None] | None = None, mobile: bool = False):
    """Retorna (controle_raiz, recarregar, obter_totais, buscar).

    recarregar(): relê boxes/cartões e redesenha. obter_totais(): dict p/ cards de resumo.
    """
    totais = {"guardado": 0.0, "meta": 0.0, "falta": 0.0, "abatido": 0.0, "qtd": 0}
    boxes_cache: list[dict] = []
    em_andamento: set[str] = set()

    coluna_banner = ft.Column(spacing=6)
    grid = ft.ResponsiveRow(spacing=12, run_spacing=12)
    titulo = ft.Row(
        visible=False,
        spacing=8,
        controls=[
            ft.Icon(ft.Icons.CREDIT_CARD_ROUNDED, color="#8B5CF6", size=18),
            ft.Text("Fatura de Cartão", size=14, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY),
            ft.Text("separe o dinheiro das faturas do cartão", size=11, color=T.TEXT_MUTED),
        ],
    )
    raiz = ft.Column(spacing=10, controls=[titulo, coluna_banner, grid])

    def _safe(ctrl):
        try:
            ctrl.update()
        except Exception:
            pass

    # ── Execução segura (trava anti-duplo-clique + loading) ────────────────────
    def _executar(chave: str, botao: ft.Control | None, acao: Callable[[], str], modal=None):
        if chave in em_andamento:
            return
        em_andamento.add(chave)
        if botao is not None:
            botao.disabled = True
            _safe(botao)
        try:
            msg = acao()
            if modal is not None:
                fechar_dialogo(page, modal)
            mostrar_feedback(page, msg, "sucesso")
            recarregar()
            if callable(ao_mudar):
                ao_mudar()
        except Exception as ex:
            mostrar_feedback(page, str(ex) or "Erro ao executar a operação.", "erro")
            if botao is not None:
                botao.disabled = False
                _safe(botao)
        finally:
            em_andamento.discard(chave)

    # ── Modais ─────────────────────────────────────────────────────────────────
    def _campo_valor(label: str, valor_inicial: float = 0.0) -> ft.TextField:
        return ft.TextField(
            label=label, prefix="R$ ", keyboard_type=ft.KeyboardType.NUMBER, autofocus=True,
            value=f"{valor_inicial:.2f}".replace(".", ",") if valor_inicial > 0 else "",
            **T.campo_estilo(),
        )

    def _ler_valor(campo: ft.TextField) -> float | None:
        try:
            v = DF.parse_valor_br(campo.value)
            if v <= 0:
                raise ValueError
            return round(v, 2)
        except ValueError:
            mostrar_feedback(page, "Informe um valor válido maior que zero.", "alerta")
            return None

    def _dialogo(titulo_txt: str, icone, cor: str, corpo: list, rotulo_ok: str, ao_confirmar):
        modal = None
        btn = ft.FilledButton(
            rotulo_ok,
            style=ft.ButtonStyle(bgcolor=cor, shape=ft.RoundedRectangleBorder(radius=8), padding=pad(h=16, v=10)),
        )
        btn.on_click = lambda _: ao_confirmar(btn, modal)
        modal = ft.AlertDialog(
            modal=True,
            title=ft.Row([ft.Icon(icone, color=cor, size=22),
                          ft.Text(titulo_txt, size=16, weight=ft.FontWeight.BOLD)], spacing=8),
            content=ft.Container(width=400, content=ft.Column(spacing=12, tight=True, controls=corpo)),
            actions=[ft.TextButton("Cancelar", on_click=lambda _: fechar_dialogo(page, modal)), btn],
        )
        abrir_dialogo(page, modal)

    def _info(txt: str, cor: str = T.TEXT_MUTED) -> ft.Container:
        return ft.Container(
            padding=pad(h=10, v=8), bgcolor=T.SURFACE_ALT, border_radius=8,
            content=ft.Text(txt, size=11.5, color=cor, weight=ft.FontWeight.W_600),
        )

    def abrir_aportar(box: dict):
        sit: DF.SituacaoBox = box["situacao"]
        campo = _campo_valor("Quanto guardar agora? (R$) *", sit.falta)

        def confirmar(btn, modal):
            v = _ler_valor(campo)
            if v is None:
                return
            _executar(f"aporte:{box['id']}", btn,
                      lambda: (db.aportar_box_fatura(box["id"], v),
                               f"{formatar_moeda(v)} guardados em '{box['nome']}'.")[1], modal)

        _dialogo(f"Guardar · {box['nome']}", ft.Icons.SAVINGS_ROUNDED, T.PRIMARY, [
            _info(f"Guardado: {formatar_moeda(sit.guardado)} · Fatura: {formatar_moeda(sit.fatura)} · "
                  f"Falta: {formatar_moeda(sit.falta)}"),
            campo,
            _info("Reserva o dinheiro sem criar nova despesa: a compra já foi contada nos Potes.", T.TEXT_MUTED),
        ], "Confirmar Aporte", confirmar)

    def abrir_retirar(box: dict):
        sit: DF.SituacaoBox = box["situacao"]
        campo = _campo_valor("Quanto devolver ao Caixa Livre? (R$) *", max(0.0, sit.guardado))

        def confirmar(btn, modal):
            v = _ler_valor(campo)
            if v is None:
                return
            ok, erro = DF.validar_retirada(sit.guardado, v)
            if not ok:
                mostrar_feedback(page, erro, "alerta")
                return
            _executar(f"retirada:{box['id']}", btn,
                      lambda: (db.retirar_box_fatura(box["id"], v),
                               f"{formatar_moeda(v)} devolvidos ao Caixa Livre.")[1], modal)

        _dialogo(f"Retirar · {box['nome']}", ft.Icons.OUTPUT_ROUNDED, T.WARNING, [
            _info(f"Saldo guardado disponível: {formatar_moeda(sit.guardado)}"),
            campo,
        ], "Confirmar Retirada", confirmar)

    def abrir_mover(box: dict):
        sit: DF.SituacaoBox = box["situacao"]
        outros = [b for b in boxes_cache if b["id"] != box["id"]]
        if not outros:
            mostrar_feedback(page, "Crie outro box de fatura para transferir o saldo.", "alerta")
            return
        destino = [str(outros[0]["id"])]
        campo = _campo_valor("Valor a mover (R$) *", max(0.0, sit.guardado))
        dd = ft.Dropdown(
            label="Mover para o box", value=destino[0],
            options=[ft.dropdown.Option(key=str(b["id"]), text=b["nome"]) for b in outros],
        )
        dd.on_change = lambda e: destino.__setitem__(0, dd.value)

        def confirmar(btn, modal):
            v = _ler_valor(campo)
            if v is None:
                return
            ok, erro = DF.validar_retirada(sit.guardado, v)
            if not ok:
                mostrar_feedback(page, erro, "alerta")
                return
            _executar(f"mover:{box['id']}", btn,
                      lambda: (db.mover_entre_boxes_fatura(box["id"], destino[0], v),
                               f"{formatar_moeda(v)} movidos entre boxes.")[1], modal)

        _dialogo(f"Mover p/ outro Box · {box['nome']}", ft.Icons.SWAP_HORIZ_ROUNDED, T.INFO, [
            _info(f"Saldo disponível: {formatar_moeda(sit.guardado)}"), dd, campo,
        ], "Mover", confirmar)

    def abrir_pagar(box: dict):
        sit: DF.SituacaoBox = box["situacao"]
        if sit.neutro or not sit.fatura_id:
            mostrar_feedback(page, "Sem fatura a pagar neste cartão.", "info")
            return
        try:
            contas = db.listar_contas() or []
        except Exception:
            contas = []
        if not contas:
            mostrar_feedback(page, "Cadastre uma conta bancária para pagar a fatura.", "alerta")
            return
        padrao = str((box.get("cartoes") or {}).get("conta_debito_id") or contas[0]["id"])
        if padrao not in {str(c["id"]) for c in contas}:
            padrao = str(contas[0]["id"])
        conta_sel = [padrao]
        campo = _campo_valor("Valor a pagar (R$) *", sit.fatura)
        dd = ft.Dropdown(
            label="Pagar com a conta", value=padrao,
            options=[ft.dropdown.Option(key=str(c["id"]), text=c.get("nome", "Conta")) for c in contas],
        )
        dd.on_change = lambda e: conta_sel.__setitem__(0, dd.value)

        def confirmar(btn, modal):
            v = _ler_valor(campo)
            if v is None:
                return
            sim = DF.calcular_pagamento(sit, v)
            if not sim["ok"]:
                mostrar_feedback(page, sim["erro"], "alerta")
                return

            def acao():
                r = db.pagar_fatura_box(box["id"], sit.fatura_id, conta_sel[0], v, date.today().isoformat())
                dt = date.today().strftime("%d/%m/%Y")
                if r.get("quitada"):
                    return f"Fatura paga: {formatar_moeda(v)} em {dt}."
                return f"Pagamento parcial de {formatar_moeda(v)} em {dt}. Restam {formatar_moeda(r.get('restante', 0))}."

            _executar(f"pagar:{box['id']}", btn, acao, modal)

        _dialogo(f"Pagar Fatura · {box['nome']}", ft.Icons.PAYMENTS_ROUNDED, "#8B5CF6", [
            _info(f"Fatura: {formatar_moeda(sit.fatura)} · vence {_fmt_data(sit.vencimento)} · "
                  f"Guardado: {formatar_moeda(sit.guardado)}"),
            dd, campo,
            _info("Aceita pagamento parcial. Debita o box e a conta; não cria despesa nos Potes.", T.TEXT_MUTED),
        ], "Confirmar Pagamento", confirmar)

    # ── Card ───────────────────────────────────────────────────────────────────
    def _botao(rotulo: str, icone, acao, cor: str, preenchido: bool = False) -> ft.Control:
        conteudo = ft.Row([ft.Icon(icone, size=15, color=T.ON_NEON if preenchido else cor),
                           ft.Text(rotulo, size=11.5, weight=ft.FontWeight.BOLD,
                                   color=T.ON_NEON if preenchido else cor)], spacing=4, tight=True)
        estilo = dict(shape=ft.RoundedRectangleBorder(radius=8), padding=pad(h=10, v=8))
        if preenchido:
            return ft.FilledButton(content=conteudo, on_click=lambda _: acao(),
                                   style=ft.ButtonStyle(bgcolor=cor, **estilo))
        return ft.OutlinedButton(content=conteudo, on_click=lambda _: acao(),
                                 style=ft.ButtonStyle(side=ft.BorderSide(1, cor), **estilo))

    def _card(box: dict) -> ft.Container:
        sit: DF.SituacaoBox = box["situacao"]
        cor_cartao = box.get("cor") or "#8B5CF6"
        cor_st = COR_STATUS[sit.status]
        if sit.neutro:
            corpo_valores = ft.Text("Sem fatura a pagar", size=14, weight=ft.FontWeight.BOLD, color=cor_st)
            barra = ft.ProgressBar(value=0, color=cor_st, bgcolor=T.SURFACE_ALT, height=8)
            linha_falta = ft.Text("Nenhuma fatura em aberto com valor.", size=11.5, color=T.TEXT_MUTED)
            if sit.guardado > 0:
                linha_falta.value = f"Você ainda tem {formatar_moeda(sit.guardado)} guardados — pode retirar."
        else:
            corpo_valores = ft.Row([
                ft.Column([ft.Text("Guardado", size=10.5, color=T.TEXT_MUTED),
                           ft.Text(formatar_moeda(sit.guardado), size=16, weight=ft.FontWeight.BOLD, color=T.PRIMARY)],
                          spacing=1, expand=True),
                ft.Column([ft.Text("Fatura", size=10.5, color=T.TEXT_MUTED),
                           ft.Text(formatar_moeda(sit.fatura), size=16, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY)],
                          spacing=1, expand=True, horizontal_alignment=ft.CrossAxisAlignment.END),
            ])
            barra = ft.ProgressBar(value=sit.pct, color=cor_st, bgcolor=T.SURFACE_ALT, height=8)
            linha_falta = ft.Text(
                "Fatura coberta!" if sit.falta <= 0 else f"Falta guardar {formatar_moeda(sit.falta)}",
                size=12, weight=ft.FontWeight.W_600, color=cor_st if sit.falta > 0 else T.PRIMARY)

        info_venc = ft.Text(
            f"{_texto_dias(sit)} · {_fmt_data(sit.vencimento)}" if sit.vencimento else "Sem vencimento definido",
            size=11.5, color=T.TEXT_MUTED)

        acoes = ft.Row(spacing=6, run_spacing=6, wrap=True, controls=[
            _botao("Guardar", ft.Icons.ADD_ROUNDED, lambda b=box: abrir_aportar(b), T.PRIMARY, True),
            _botao("Retirar", ft.Icons.OUTPUT_ROUNDED, lambda b=box: abrir_retirar(b), T.WARNING),
            _botao("Mover p/ outro Box", ft.Icons.SWAP_HORIZ_ROUNDED, lambda b=box: abrir_mover(b), T.INFO),
            _botao("Pagar Fatura", ft.Icons.PAYMENTS_ROUNDED, lambda b=box: abrir_pagar(b), "#8B5CF6"),
        ])

        return ft.Container(
            col={"xs": 12, "sm": 12, "md": 6, "lg": 4},
            padding=pad(h=14, v=11), bgcolor=T.SURFACE, border_radius=14, border=borda(1, cor_st),
            content=ft.Column(spacing=7, controls=[
                ft.Row([
                    ft.Icon(ft.Icons.CREDIT_CARD_ROUNDED, color=cor_cartao, size=20),
                    ft.Text((box.get("cartoes") or {}).get("nome") or box["nome"], size=14.5,
                            weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY, expand=True,
                            max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Container(padding=pad(h=8, v=2), border_radius=10, bgcolor=T.SURFACE_ALT,
                                 border=borda(1, cor_st),
                                 content=ft.Text(sit.rotulo, size=10.5, weight=ft.FontWeight.BOLD, color=cor_st)),
                ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                corpo_valores,
                barra,
                ft.Row([
                    ft.Container(content=linha_falta, expand=True),
                    info_venc,
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, spacing=6),
                acoes,
            ]),
        )

    # ── Banner "Criar DemBox Fatura para seus cartões" (compacto) ──────────────
    def _criar_para(cartao: dict, botao: ft.Control | None = None):
        _executar(f"criar:{cartao['id']}", botao,
                  lambda: (db.criar_box_fatura(str(cartao["id"])),
                           f"DemBox Fatura criado para {cartao.get('nome', 'o cartão')}.")[1])

    def _desenhar_banner(sem_box: list[dict]):
        coluna_banner.controls.clear()
        if not sem_box:
            return
        chips = []
        for c in sem_box:
            b = ft.OutlinedButton(
                content=ft.Row([ft.Icon(ft.Icons.ADD_ROUNDED, size=13, color="#8B5CF6"),
                                ft.Text(c.get("nome", "Cartão"), size=11, weight=ft.FontWeight.BOLD,
                                        color="#8B5CF6")], spacing=3, tight=True),
                style=ft.ButtonStyle(side=ft.BorderSide(1, "#8B5CF6"), shape=ft.RoundedRectangleBorder(radius=16),
                                     padding=pad(h=10, v=4)))
            b.on_click = lambda _, cc=c, bb=b: _criar_para(cc, bb)
            chips.append(b)
        coluna_banner.controls.append(ft.Container(
            padding=pad(h=12, v=7), bgcolor=T.SURFACE_ALT, border_radius=10, border=borda(1, "#8B5CF6"),
            content=ft.Row(
                spacing=8,
                run_spacing=6,
                wrap=True,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Row([
                        ft.Icon(ft.Icons.ADD_CARD_ROUNDED, color="#8B5CF6", size=16),
                        ft.Text("Criar DemBox Fatura:", size=11.5, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY),
                    ], spacing=5, tight=True),
                    *chips,
                ],
            )))

    # ── Recarregar ─────────────────────────────────────────────────────────────
    def buscar():
        """I/O puro (pode rodar em thread). Retorna (boxes, cartoes_sem_box)."""
        try:
            return db.listar_boxes_fatura(), db.listar_cartoes_sem_box_fatura()
        except Exception as ex:
            print(f"[DemBoxFatura] erro ao carregar: {ex}")
            return [], []

    def recarregar(dados=None):
        boxes, sem_box = dados if dados is not None else buscar()
        boxes_cache[:] = boxes
        grid.controls = [_card(b) for b in boxes]
        _desenhar_banner(sem_box)
        titulo.visible = bool(boxes or sem_box)
        resumo = DF.somar_resumo(b["situacao"] for b in boxes)
        totais.update(guardado=resumo["guardado"], meta=resumo["meta"], falta=resumo["falta"], qtd=len(boxes),
                      abatido=round(sum(DF.calcular_abatido(b["movimentos"]) for b in boxes), 2))
        for c in (titulo, coluna_banner, grid, raiz):
            _safe(c)

    return raiz, recarregar, (lambda: dict(totais)), buscar
