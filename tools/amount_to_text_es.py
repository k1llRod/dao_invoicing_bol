import logging

_logger = logging.getLogger(__name__)

# Basandonos en http://www.lawebdelprogramador.com/foros/Python/297286-Transformar-numeros-a-literales.html
# y en amount_to_text_es de Odoo en TOOLS
#-------------------------------------------------------------
#ESPANIOL
#-------------------------------------------------------------

indicador = [("", ""), ("MIL", "MIL"), ("MILLON", "MILLONES"), ("MIL", "MIL"), ("BILLON", "BILLONES")]
lista_centana = ["", ("CIEN", "CIENTO"), "DOSCIENTOS", "TRESCIENTOS", "CUATROCIENTOS", "QUINIENTOS", "SEISCIENTOS", "SETECIENTOS", "OCHOCIENTOS", "NOVECIENTOS"]
lista_decena = ["", ("DIEZ", "ONCE", "DOCE", "TRECE", "CATORCE", "QUINCE", "DIECISEIS", "DIECISIETE", "DIECIOCHO", "DIECINUEVE"),
                    ("VEINTE", "VEINTI"), ("TREINTA", "TREINTA Y "), ("CUARENTA", "CUARENTA Y "),
                    ("CINCUENTA", "CINCUENTA Y "), ("SESENTA", "SESENTA Y "),
                    ("SETENTA", "SETENTA Y "), ("OCHENTA", "OCHENTA Y "),
                    ("NOVENTA", "NOVENTA Y ")
            ]
lista_unidad = ["", ("UN", "UNO"), "DOS", "TRES", "CUATRO", "CINCO", "SEIS", "SIETE", "OCHO", "NUEVE"]


def amount_to_text(number, currency):
    """
    Recibe un valor numerico (float) que representa un monto y un currency (nombre moneda, ejm: Bolivianos).
    Retorna un valor texto monto LITERAL
    ejemplo: .amount_to_text(411641.123, 'Bolivianos') -> CUATROCIENTOS ONCE MIL SEISCIENTOS CUARENTA Y UNO 12/100 Bolivianos
    Ya que si usamos el de ODOO, obtenemos en Ingles
    usando Odoo Tools, (4968.00, 'Bolivianos') -> Four Thousand, Nine Hundred Sixty-Eight Bolivianos and Zero Cent
    """
    # Primero transformamos el numero a string con 2 decimales y con el formato de punto separador de decimales
    number = '%.2f' % number
    units_name = currency
    # Obtenemos una lista de valores por split del separador de decimales (que es el '.' al trasnformarlo a string)
    list = str(number).split('.')
    # Codigo de TOOLs de ODOO para transformar en Ingles
    # start_word = english_number(int(list[0]))
    # end_word = english_number(int(list[1]))
    # cents_number = int(list[1])
    # cents_name = (cents_number > 1) and 'Cents' or 'Cent'

    # return ' '.join(filter(None, [start_word, units_name, (start_word or units_name) and (end_word or cents_name) and 'and', end_word, cents_name]))

    # Ponemos en las respectivas variables la parte entera y la parte decimal
    entero = int(list[0])
    decimal = int(list[1])

    #print 'entero : ',entero
    #print 'decimal : ',decimal

    contador = 0
    numero_letras = ""

    while entero > 0:
        # Obtenemos el mod 1000 del numero
        a = entero % 1000

        # Si el contador es 0, se le pasa a la funcion _convierte_cifra al parametro sw =1
        # esto por si el valor entero es simplemente 1, por tanto se debe mostrar UN Bolivianos.
        # caso contrario se pasa el valor sw =0 por si el entero es compuesto , ej: 21 Ventiuno
        if contador == 0:
            en_letras = _convierte_cifra(a, 1).strip()
        else:
            en_letras = _convierte_cifra(a, 0).strip()

        if a == 0:
            numero_letras = en_letras+" "+numero_letras
        elif a == 1:
            if contador in (1, 3):
                numero_letras = indicador[contador][0]+" "+numero_letras
            else:
                numero_letras = en_letras+" "+indicador[contador][0]+" "+numero_letras
        else:
            numero_letras = en_letras+" "+indicador[contador][1]+" "+numero_letras

        numero_letras = numero_letras.strip()

        # Aumentamos el contador.
        contador = contador + 1
        # obtenemos la parte entera de la division del valor del entero entre 1000.
        entero = int(entero / 1000)

    # numero_letras = numero_letras + " con " + str(decimal) + "/100"

    # si longitud de la parte decimal es 1 debemos adicionar un 0 a la izquierda , ejemplo 1 deberia ser 01/100 en lugar de 1/100
    # 1 centavo es distinto a 10 centavos 01/100 <> 10/100
    # usamos rjust de python como padding
    numero_letras = "%s %s/100 %s" % (numero_letras, str(decimal).rjust(2, '0'), units_name)

    # print 'numero: ', number
    # print numero_letras

    return numero_letras


def _convierte_cifra(numero, sw):
    centena = int(numero / 100)
    decena = int((numero - (centena * 100)) / 10)
    unidad = int(numero - (centena * 100 + decena * 10))
    #print "centena: ",centena, "decena: ",decena,'unidad: ',unidad

    texto_centena = ""
    texto_decena = ""
    texto_unidad = ""

    #Validad las centenas
    texto_centena = lista_centana[centena]
    if centena == 1:
        if (decena + unidad) != 0:
            texto_centena = texto_centena[1]
        else:
            texto_centena = texto_centena[0]

    #Valida las decenas
    texto_decena = lista_decena[decena]
    if decena == 1:
        texto_decena = texto_decena[unidad]
    elif decena > 1:
        if unidad != 0:
            texto_decena = texto_decena[1]
        else:
            texto_decena = texto_decena[0]
    #Validar las unidades
    #print "texto_unidad: ",texto_unidad
    if decena != 1:
        texto_unidad = lista_unidad[unidad]
        if unidad == 1:
            texto_unidad = texto_unidad[sw]

    return "%s %s %s" % (texto_centena, texto_decena, texto_unidad)
