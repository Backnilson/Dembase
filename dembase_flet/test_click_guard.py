"""
Teste do core/click_guard.py (sem cliente Flet): simula o empilhamento de cliques.
Executar:  python test_click_guard.py
"""
import asyncio
import time

import flet as ft

from core import click_guard as cg


class FakePage:
    def __init__(self):
        self.overlay = []
        self.route = "/dashboard"
        self.updates = 0

    def update(self, *a):
        self.updates += 1


class FakeBtn:
    """Imita um botão: handler configurável, sem árvore Flet."""

    def __init__(self, page, handler):
        self.page = page
        self._i = 101
        self.on_click = handler
        self.disabled = False
        self.opacity = 1.0

    def update(self):
        pass


def _preparar(orig):
    cg._orig_trigger = orig
    cg._pagina_de = lambda c: c.page
    # overlay fake (não depende de árvore Flet)
    class Ovl:
        ignore_interactions = True
        opacity = 0
        historico = []

        def update(self):
            Ovl.historico.append((self.ignore_interactions, self.opacity))

    def garantir(page, est):
        if est.overlay is None:
            est.overlay = Ovl()
        return est.overlay

    cg._garantir_overlay = garantir
    return Ovl


async def cenario_sync_bloqueante():
    chamadas = []

    async def orig(self, nome, dados, e=None):
        chamadas.append(time.perf_counter())
        time.sleep(0.4)  # handler síncrono pesado bloqueando o loop (como o Supabase)

    Ovl = _preparar(orig)
    page = FakePage()
    btn = FakeBtn(page, lambda e: None)
    # 6 cliques "empilhados" na fila durante o congelamento
    await asyncio.gather(*[cg._trigger_event_guardado(btn, "click", None) for _ in range(6)])
    assert len(chamadas) == 1, f"esperado 1 execução, houve {len(chamadas)}"
    assert Ovl.historico[0] == (False, 1), f"overlay deveria ligar antes do handler: {Ovl.historico}"
    assert Ovl.historico[-1] == (True, 0), "overlay deveria desligar no final"
    assert btn.disabled is False and btn.opacity == 1.0, "botão deveria ser restaurado"
    print("OK  6 cliques empilhados -> 1 execução; overlay liga/desliga; botão restaurado")


async def cenario_erro():
    async def orig(self, nome, dados, e=None):
        raise RuntimeError("falha de rede simulada")

    Ovl = _preparar(orig)
    page = FakePage()
    btn = FakeBtn(page, lambda e: None)
    try:
        await cg._trigger_event_guardado(btn, "click", None)
    except RuntimeError:
        pass
    est = cg._estado(page)
    assert not est.em_voo, "trava deveria ser liberada após erro"
    assert Ovl.historico[-1] == (True, 0), "overlay deveria desligar após erro"
    assert btn.disabled is False
    # Novo clique após o erro precisa funcionar (depois da janela de descarte)
    await asyncio.sleep(cg._JANELA_DESCARTE_S + 0.05)
    n = []

    async def orig2(self, nome, dados, e=None):
        n.append(1)

    cg._orig_trigger = orig2
    await cg._trigger_event_guardado(btn, "click", None)
    assert n == [1]
    print("OK  erro no handler libera trava, overlay e botão; clique seguinte funciona")


async def cenario_async_lento():
    chamadas = []

    async def orig(self, nome, dados, e=None):
        chamadas.append(1)
        await asyncio.sleep(0.5)

    Ovl = _preparar(orig)
    page = FakePage()
    btn = FakeBtn(page, orig)  # coroutine function -> caminho async
    await asyncio.gather(*[cg._trigger_event_guardado(btn, "click", None) for _ in range(6)])
    assert len(chamadas) == 1
    assert any(h == (False, 1) for h in Ovl.historico), "overlay deveria aparecer em ação async lenta"
    assert Ovl.historico[-1] == (True, 0)
    print("OK  handler async lento: 1 execução, overlay tardio exibido e removido")


async def cenario_async_rapido():
    async def orig(self, nome, dados, e=None):
        pass

    Ovl = _preparar(orig)
    page = FakePage()
    btn = FakeBtn(page, orig)
    await cg._trigger_event_guardado(btn, "click", None)
    assert Ovl.historico == [] or Ovl.historico == [], "ação async rápida não deve piscar overlay"
    print("OK  handler async rápido não pisca overlay")


async def cenario_navegacao():
    async def orig(self, nome, dados, e=None):
        cg.nav_iniciada(btn.page)  # como page.navigate()

    Ovl = _preparar(orig)
    page = FakePage()
    btn = FakeBtn(page, lambda e: None)

    async def fim_nav():
        await asyncio.sleep(0.3)
        cg.nav_concluida(page)

    t0 = time.perf_counter()
    asyncio.create_task(fim_nav())
    await cg._trigger_event_guardado(btn, "click", None)
    dt = time.perf_counter() - t0
    assert dt >= 0.28, f"overlay deveria esperar a navegação ({dt:.2f}s)"
    assert Ovl.historico[-1] == (True, 0)
    print(f"OK  overlay aguarda fim da navegação ({dt:.2f}s) e depois some")


async def main():
    orig_pagina, orig_garantir, orig_trig = cg._pagina_de, cg._garantir_overlay, cg._orig_trigger
    for cen in (cenario_sync_bloqueante, cenario_erro, cenario_async_lento,
                cenario_async_rapido, cenario_navegacao):
        await cen()
        await asyncio.sleep(cg._JANELA_DESCARTE_S + 0.05)
    cg._pagina_de, cg._garantir_overlay, cg._orig_trigger = orig_pagina, orig_garantir, orig_trig
    print("TODOS OS TESTES DO CLICK_GUARD PASSARAM")


if __name__ == "__main__":
    asyncio.run(main())
