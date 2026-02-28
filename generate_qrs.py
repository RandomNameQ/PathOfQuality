import qrcode
from PIL import Image

data = {
    "cloudtips": "https://pay.cloudtips.ru/p/c837cb8f",
    "ton": "UQBYbeE_Y27_11-MSFqO4Udr-YAihHuAEznyCQ5EHhevR71R",
    "btc": "bc1qvtsc8p7stzpj88hyhd2z45ps5q62auxceztmxf",
    "eth": "0x17e06f02FA09B5E1314e46B775d2825B480a57f5"
}

for name, url in data.items():
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=4,
        border=1,
    )
    qr.add_data(url)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    img.save(f"assets/qr/{name}.png")

print("Generated 4 QR codes in assets/qr/")
