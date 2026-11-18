# 3D-Prototyp (V-034, Stand 18.11.2026)

Eigene Low-Poly-Szene mit three.js, gerendert von Chromium ohne Grafikkarte (SwiftShader). Nur Muster aus den Referenzvideos
des Inhabers (Stil), keine Inhalte oder Figuren der Vorlagen.

    npm install three@0.160.0 playwright
    python3 -m http.server 8765 --bind 127.0.0.1 &
    node render.js 4 2        # 4 Sekunden, Pixelfaktor 2 (1080x1920) -> frames/f0000.png ...
    ffmpeg -framerate 30 -i frames/f%04d.png -c:v libx264 -pix_fmt yuv420p out.mp4

Messwert: 120 Bilder in 28,7 s bei 1080x1920 (Sandbox), also etwa 0,24 s je Bild. Ein 60-Sekunden-Video (1800 Bilder) braucht rund 7 Minuten Rendern.
Offen: Szenen aus JSON statt fest im Code, Stimme, mehrere Figuren und Kulissen, GitHub Action.
