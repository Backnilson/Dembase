"""Teste rápido do padrão de navegação correto no Flet 1.0"""
import flet as ft

def main(page: ft.Page):
    page.title = "Teste Flet 1.0"
    page.bgcolor = "#0B0F19"
    page.window.width = 480
    page.window.height = 680

    def ir_para_b(_):
        page.views.append(
            ft.View(
                route="/b",
                bgcolor="#151D2C",
                controls=[
                    ft.Container(
                        content=ft.Column([
                            ft.Text("Tela B funcionou!", color="white", size=24),
                            ft.FilledButton("Voltar", on_click=lambda _: (page.views.pop(), page.update())),
                        ]),
                        alignment=ft.alignment.center,
                        expand=True,
                    )
                ],
                padding=20,
            )
        )
        page.update()

    def on_route_change(e):
        print(f"Route changed: {page.route}")

    page.on_route_change = on_route_change

    # Adiciona a view inicial diretamente
    page.views.clear()
    page.views.append(
        ft.View(
            route="/a",
            bgcolor="#0B0F19",
            controls=[
                ft.Container(
                    content=ft.Column([
                        ft.Text("Tela A - Flet 1.0", color="#10B981", size=28, weight=ft.FontWeight.BOLD),
                        ft.Text("Navegação funcionando!", color="white", size=14),
                        ft.FilledButton("Ir para B", on_click=ir_para_b),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    ),
                    alignment=ft.alignment.center,
                    expand=True,
                    bgcolor="#0B0F19",
                )
            ],
            padding=20,
        )
    )
    page.update()

ft.run(main)
