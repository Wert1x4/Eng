"""Address and QR code for opening Lumen from a phone on the same Wi-Fi."""

from lumen.qrcodegen import QrCode


def qr_svg(text):
    qr = QrCode.encode_text(text, QrCode.Ecc.MEDIUM)
    size = qr.get_size()
    border = 2
    dim = size + border * 2
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {dim} {dim}" shape-rendering="crispEdges">',
        f'<rect width="{dim}" height="{dim}" fill="#ffffff"/>',
    ]
    for y in range(size):
        x = 0
        while x < size:
            if not qr.get_module(x, y):
                x += 1
                continue
            start = x
            while x < size and qr.get_module(x, y):
                x += 1
            parts.append(
                f'<rect x="{start + border}" y="{y + border}" width="{x - start}" height="1" fill="#14683a"/>'
            )
    parts.append("</svg>")
    return "".join(parts)
