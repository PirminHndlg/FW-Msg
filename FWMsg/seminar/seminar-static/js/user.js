function getQRCode(div, url) {
    const qrcode = new QRCode(div, {
        text: url,
        width: 128,   // Width of the QR code
        height: 128,  // Height of the QR code
        colorDark: "#000000",  // Dark color
        colorLight: "#ffffff", // Light color
        correctLevel: QRCode.CorrectLevel.H  // Error correction level
    });

}