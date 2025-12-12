from flask import Flask, request
import xml.etree.ElementTree as ET
import sys
import chilkat2
from datetime import datetime

app = Flask(__name__)


@app.route('/xml-2-xmldsig', methods=['POST'])
def parse_xml2():
    xml_data = request.data
    root = ET.fromstring(xml_data)

    cabecera = root.find('cabecera')

    nit_emisor = cabecera.find('nitEmisor').text
    razon_social_emisor = cabecera.find('razonSocialEmisor').text
    municipio = cabecera.find('municipio').text
    telefono = cabecera.find('telefono').text
    numero_factura = cabecera.find('numeroFactura').text
    cuf = cabecera.find('cuf').text
    cufd = cabecera.find('cufd').text
    codigoSucursal = cabecera.find('codigoSucursal').text
    direccion = cabecera.find('direccion').text
    codigoPuntoVenta = cabecera.find('codigoPuntoVenta').text
    fechaEmision = cabecera.find('fechaEmision').text
    nombreRazonSocial = cabecera.find('nombreRazonSocial').text
    codigoTipoDocumentoIdentidad = cabecera.find('codigoTipoDocumentoIdentidad').text
    numeroDocumento = cabecera.find('numeroDocumento').text
    complemento = cabecera.find('complemento').text
    codigoCliente = cabecera.find('codigoCliente').text
    codigoMetodoPago = cabecera.find('codigoMetodoPago').text
    numeroTarjeta = cabecera.find('numeroTarjeta').text
    if numeroTarjeta is None or numeroTarjeta.strip() == '':
        numeroTarjeta = '0'
    montoTotal = cabecera.find('montoTotal').text
    montoTotalSujetoIva = cabecera.find('montoTotalSujetoIva').text
    codigoMoneda = cabecera.find('codigoMoneda').text
    tipoCambio = cabecera.find('tipoCambio').text
    montoTotalMoneda = cabecera.find('montoTotalMoneda').text
    montoGiftCard = cabecera.find('montoGiftCard').text
    descuentoAdicional = cabecera.find('descuentoAdicional').text
    if descuentoAdicional is None or descuentoAdicional.strip() == '':
        descuentoAdicional = '0.00'
    codigoExcepcion = cabecera.find('codigoExcepcion').text
    if codigoExcepcion is None or codigoExcepcion.strip() == '':
        codigoExcepcion = '0'
    cafc = cabecera.find('cafc').text
    leyenda = cabecera.find('leyenda').text
    usuario = cabecera.find('usuario').text
    codigoDocumentoSector = cabecera.find('codigoDocumentoSector').text

    detalle = root.find('detalle')

    actividadEconomica = detalle.find('actividadEconomica').text
    codigoProductoSin = detalle.find('codigoProductoSin').text
    codigoProducto = detalle.find('codigoProducto').text
    descripcion = detalle.find('descripcion').text
    cantidad = detalle.find('cantidad').text
    unidadMedida = detalle.find('unidadMedida').text
    precioUnitario = detalle.find('precioUnitario').text
    montoDescuento = detalle.find('montoDescuento').text
    subTotal = detalle.find('subTotal').text
    numeroSerie = detalle.find('numeroSerie').text
    numeroImei = detalle.find('numeroImei').text

    # Add more variables as needed

    # Create a response string with the extracted variables
    response = f"""
    nit_emisor: {nit_emisor}
    razon_social_emisor: {razon_social_emisor}
    municipio: {municipio}
    telefono: {telefono}
    numero_factura: {numero_factura}
    cuf: {cuf}
    cufd: {cufd}
    codigoSucursal: {codigoSucursal}
    direccion: {direccion}
    codigoPuntoVenta: {codigoPuntoVenta}
    fechaEmision: {fechaEmision}
    nombreRazonSocial: {nombreRazonSocial}
    codigoTipoDocumentoIdentidad: {codigoTipoDocumentoIdentidad}
    numeroDocumento: {numeroDocumento}
    complemento: {complemento}
    codigoCliente: {codigoCliente}
    codigoMetodoPago: {codigoMetodoPago}
    numeroTarjeta: {numeroTarjeta}
    montoTotal: {montoTotal}
    montoTotalSujetoIva: {montoTotalSujetoIva}
    codigoMoneda: {codigoMoneda}
    tipoCambio: {tipoCambio}
    montoTotalMoneda: {montoTotalMoneda}
    montoGiftCard: {montoGiftCard}
    descuentoAdicional: {descuentoAdicional}
    codigoExcepcion: {codigoExcepcion}
    cafc: {cafc}
    leyenda: {leyenda}
    usuario: {usuario}
    codigoDocumentoSector: {codigoDocumentoSector}
    actividadEconomica: {actividadEconomica}
    codigoProductoSin: {codigoProductoSin}
    codigoProducto: {codigoProducto}
    descripcion: {descripcion}
    cantidad: {cantidad}
    unidadMedida: {unidadMedida}
    precioUnitario: {precioUnitario}
    montoDescuento: {montoDescuento}
    subTotal: {subTotal}
    numeroSerie: {numeroSerie}
    numeroImei: {numeroImei}
    """

    # Handle GET requests to the '/get_xml_values' endpoint
    if nit_emisor:
        # This example assumes the Chilkat API to have been previously unlocked.
        # See Global Unlock Sample for sample code.

        success = True

        # Use this online tool to generate code from sample XML:
        # Generate Code to Create XML

        xml = chilkat2.Xml()
        xml.Tag = "facturaElectronicaCompraVenta"
        xml.AddAttribute("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
        xml.AddAttribute("xsi:noNamespaceSchemaLocation", "facturaElectronicaCompraVenta.xsd")
        xml.UpdateChildContent("cabecera|nitEmisor", nit_emisor)
        xml.UpdateChildContent("cabecera|razonSocialEmisor", razon_social_emisor)
        xml.UpdateChildContent("cabecera|municipio", municipio)
        xml.UpdateChildContent("cabecera|telefono", telefono)
        xml.UpdateChildContent("cabecera|numeroFactura", numero_factura)
        xml.UpdateChildContent("cabecera|cuf", cuf)
        xml.UpdateChildContent("cabecera|cufd", cufd)
        xml.UpdateChildContent("cabecera|codigoSucursal", codigoSucursal)
        xml.UpdateChildContent("cabecera|direccion", direccion)
        xml.UpdateChildContent("cabecera|codigoPuntoVenta", codigoPuntoVenta)
        xml.UpdateChildContent("cabecera|fechaEmision", fechaEmision)
        xml.UpdateChildContent("cabecera|nombreRazonSocial", nombreRazonSocial)
        xml.UpdateChildContent("cabecera|codigoTipoDocumentoIdentidad", codigoTipoDocumentoIdentidad)
        xml.UpdateChildContent("cabecera|numeroDocumento", numeroDocumento)
        xml.UpdateAttrAt("cabecera|complemento", True, "xsi:nil", "true")
        xml.UpdateChildContent("cabecera|codigoCliente", codigoCliente)
        xml.UpdateChildContent("cabecera|codigoMetodoPago", codigoMetodoPago)
        xml.UpdateChildContent("cabecera|numeroTarjeta", numeroTarjeta)
        xml.UpdateChildContent("cabecera|montoTotal", montoTotal)
        xml.UpdateChildContent("cabecera|montoTotalSujetoIva", montoTotalSujetoIva)
        xml.UpdateChildContent("cabecera|codigoMoneda", codigoMoneda)
        xml.UpdateChildContent("cabecera|tipoCambio", tipoCambio)
        xml.UpdateChildContent("cabecera|montoTotalMoneda", montoTotalMoneda)
        xml.UpdateAttrAt("cabecera|montoGiftCard", True, "xsi:nil", "true")
        xml.UpdateChildContent("cabecera|descuentoAdicional", descuentoAdicional)
        xml.UpdateChildContent("cabecera|codigoExcepcion", codigoExcepcion)
        xml.UpdateAttrAt("cabecera|cafc", True, "xsi:nil", "true")
        xml.UpdateChildContent("cabecera|leyenda", leyenda)
        xml.UpdateChildContent("cabecera|usuario", usuario)
        xml.UpdateChildContent("cabecera|codigoDocumentoSector", codigoDocumentoSector)
        xml.UpdateChildContent("detalle|actividadEconomica", actividadEconomica)
        xml.UpdateChildContent("detalle|codigoProductoSin", codigoProductoSin)
        xml.UpdateChildContent("detalle|codigoProducto", codigoProducto)
        xml.UpdateChildContent("detalle|descripcion", descripcion)
        xml.UpdateChildContent("detalle|cantidad", cantidad)
        xml.UpdateChildContent("detalle|unidadMedida", unidadMedida)
        xml.UpdateChildContent("detalle|precioUnitario", precioUnitario)
        xml.UpdateChildContent("detalle|montoDescuento", montoDescuento)
        xml.UpdateChildContent("detalle|subTotal", subTotal)
        xml.UpdateAttrAt("detalle|numeroSerie", True, "xsi:nil", "true")
        xml.UpdateAttrAt("detalle|numeroImei", True, "xsi:nil", "true")

        gen = chilkat2.XmlDSigGen()

        gen.SigLocation = "facturaElectronicaCompraVenta"
        gen.SigLocationMod = 0
        gen.SigNamespacePrefix = ""
        gen.SigNamespaceUri = "http://www.w3.org/2000/09/xmldsig#"
        gen.SignedInfoCanonAlg = "C14N"
        gen.SignedInfoDigestMethod = "sha256"

        gen.AddSameDocRef("", "sha256", "C14N_WithComments", "", "")

        # Provide your certificate + private key. (PFX password is test123)
        cert = chilkat2.Cert()
        success = cert.LoadPfxFile("softoken.p12", "Lobyta1!")
        if (success != True):
            print(cert.LastErrorText)
            sys.exit()

        gen.SetX509Cert(cert, True)

        gen.KeyInfoType = "X509Data"
        gen.X509Type = "Certificate"

        gen.Behaviors = "EnvelopedTransformFirst"

        # Load XML to be signed...
        sbXml = chilkat2.StringBuilder()
        xml.EmitCompact = True
        xml.GetXmlSb(sbXml)

        # Sign the XML...
        success = gen.CreateXmlDSigSb(sbXml)
        if (success != True):
            print(gen.LastErrorText)
            sys.exit()

        # -----------------------------------------------

        timestamp = datetime.now().strftime('%Y-%m-%d-%H-%M-%S')
        # Generate the filename
        filename = f'factura_{numero_factura}_{timestamp}.xml'
        # Save the signed XML to a file.
        success = sbXml.WriteFile(filename, "utf-8", True)

        print(sbXml.GetAsString())

        # ----------------------------------------
        # Verify the signatures we just produced...
        verifier = chilkat2.XmlDSig()
        success = verifier.LoadSignatureSb(sbXml)
        if (success != True):
            print(verifier.LastErrorText)
            sys.exit()

        numSigs = verifier.NumSignatures
        verifyIdx = 0
        while verifyIdx < numSigs:
            verifier.Selector = verifyIdx
            verified = verifier.VerifySignature(True)
            if (verified != True):
                print(verifier.LastErrorText)
                sys.exit()

            verifyIdx = verifyIdx + 1

        return filename
    else:
        return 'No se especificó el NIT emisor en el XML enviado'


if __name__ == '__main__':
    app.run(debug=True)
