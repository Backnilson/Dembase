"""
=============================================================================
DemBase v3 — build_pwa.py
Script oficial de compilação estática do PWA (Flet 1.0.1 + Pyodide/WASM).
Gera o diretório 'dist/' pronto para publicação no Cloudflare Pages, Vercel
ou GitHub Pages, com:
- Nome configurado como "DemBase Finanças"
- Ícones personalizados (192, 512, maskable e apple-touch-icon)
- manifest.json no padrão PWA standalone
- Arquivo _redirects para SPA routing (evitando erro 404 em recargas)
=============================================================================
"""
import os
import sys
import shutil
import subprocess

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
ASSETS_DIR = os.path.join(CURRENT_DIR, "assets")
ICONS_DIR = os.path.join(ASSETS_DIR, "icons")
DIST_DIR = os.path.join(PROJECT_ROOT, "dist")

def main():
    print("==================================================================")
    print("DEMBASE v3 — INICIANDO BUILD DO PWA ESTÁTICO (FLET 1.0.1)")
    print("==================================================================")

    # Limpeza prévia para evitar recursão no empacotamento
    for pasta_antiga in [os.path.join(CURRENT_DIR, "dist"), DIST_DIR]:
        if os.path.exists(pasta_antiga):
            shutil.rmtree(pasta_antiga, ignore_errors=True)

    # 1. Certifica que os ícones foram gerados
    icone_192 = os.path.join(ICONS_DIR, "icon-192.png")
    if not os.path.exists(icone_192):
        print("\n[1/4] Gerando ícones PWA a partir do logo.svg...")
        script_icones = os.path.join(CURRENT_DIR, "scripts", "gerar_icones_pwa.py")
        subprocess.run([sys.executable, script_icones], check=True)
    else:
        print("\n[1/4] Ícones PWA já presentes em assets/icons/.")

    # 2. Executa o flet publish
    print("\n[2/4] Executando 'flet publish' com WebAssembly e CanvasKit...")
    main_py = os.path.join(CURRENT_DIR, "main.py")
    flet_bin = shutil.which("flet")
    base_cmd = [flet_bin] if flet_bin else [sys.executable, "-c", "from flet.cli import main; main()"]
    cmd = base_cmd + [
        "publish", main_py,
        "--distpath", DIST_DIR,
        "-a", ASSETS_DIR,
        "--app-name", "DemBase Finanças",
        "--app-short-name", "DemBase Finanças",
        "--app-description", "Controle financeiro pessoal com regra 50/30/20",
        "--pwa-background-color", "#0F172A",
        "--pwa-theme-color", "#0F172A",
        "--web-renderer", "canvaskit",
        "--route-url-strategy", "path"
    ]
    res = subprocess.run(cmd, check=True)
    if res.returncode != 0:
        print("[ERRO] Falha na compilação do flet publish.")
        sys.exit(1)

    # 3. Injeta ícones customizados e redirects no dist
    print("\n[3/4] Injetando ícones customizados e arquivo _redirects em dist/...")
    dist_icons = os.path.join(DIST_DIR, "icons")
    os.makedirs(dist_icons, exist_ok=True)

    for item in os.listdir(ICONS_DIR):
        src = os.path.join(ICONS_DIR, item)
        dst = os.path.join(dist_icons, item)
        if os.path.isfile(src):
            shutil.copy2(src, dst)

    # Garantir apple-touch-icon-192.png
    src_apple = os.path.join(ICONS_DIR, "apple-touch-icon.png")
    if os.path.exists(src_apple):
        shutil.copy2(src_apple, os.path.join(dist_icons, "apple-touch-icon-192.png"))

    # Copiar favicon e _redirects
    fav_src = os.path.join(ASSETS_DIR, "favicon.png")
    if os.path.exists(fav_src):
        shutil.copy2(fav_src, os.path.join(DIST_DIR, "favicon.png"))

    red_src = os.path.join(ASSETS_DIR, "_redirects")
    if os.path.exists(red_src):
        shutil.copy2(red_src, os.path.join(DIST_DIR, "_redirects"))

    # 4. Verificação de integridade
    print("\n[4/4] Verificando integridade dos arquivos gerados em dist/:")
    arquivos_obrigatorios = [
        "index.html",
        "manifest.json",
        "flutter_service_worker.js",
        "_redirects",
        "app.tar.gz",
        "favicon.png",
        "icons/icon-192.png",
        "icons/icon-512.png"
    ]
    todos_ok = True
    for arq in arquivos_obrigatorios:
        caminho = os.path.join(DIST_DIR, arq)
        if os.path.exists(caminho):
            tamanho = os.path.getsize(caminho)
            print(f"  [OK] {arq:<30} ({tamanho:>10,} bytes)")
        else:
            print(f"  [FALHA] Arquivo obrigatório não encontrado: {arq}")
            todos_ok = False

    if todos_ok:
        print("\n==================================================================")
        print("BUILD PWA CONCLUÍDO COM 100% DE SUCESSO!")
        print(f"Diretório gerado: {DIST_DIR}")
        print("Pronto para publicação no Cloudflare Pages, Vercel ou GitHub Pages.")
        print("==================================================================")
    else:
        print("\n[AVISO] Alguns arquivos não foram encontrados no dist.")
        sys.exit(1)

if __name__ == "__main__":
    main()
