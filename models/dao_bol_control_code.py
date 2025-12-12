# -*- coding: utf-8 -*-
# ############################
# Author: Carlos Diego Paravicini Bilbao
# Company: DAO-SYSTEMS
# Description: Implementacion de los pasos necesario especificados por el SIN (SERVICIO IMPUESTOS NACIONALES de BOLIVIA) para generar el CODIGO de CONTROL de una factura.
# ############################

# Para manejar regular expressions
import re
# Para manejar algoritmos de verhoeff (digito verificador) y cifrar (Alleged ARC4)
import stdnum
from stdnum import verhoeff
from Crypto.Cipher import ARC4

# Para manejar el PRINT en modo debug
# from openerp.http import request


class BolTransaction(object):
    """
    Clase que representa una transaccion de factura con normativa Boliviana para poder generar un codigo de verificacion.
    http://impuestosgovbo.readyhosting.com/Informacion/Biblioteca/gestion2006/Tetrap_NSF3.pdf
    VERSION 1 a la 6
    PASO 1 (INICIALIZAMOS los valores)
    EJEMPLO: usando datos: AuthNumber : 7904006098968, ProportionKey: m3dcSc)Dg#SN}prtK=9xn[m+pgAxL%N67G}QfwNZM+)IzCnvP$T*qjEKhmJnaDHm
    EJEMPLO SIN : AuthNumber: 29010915579, ProportionKey:SeSaMo, InvoiceNumer: 1503, fecha; 20070610, NIT: 37343140179, monto: 4968
    """
    # Inicializacion de la clase
    def __init__(self, strAuthNumber, intInvoiceNumber, intClientNIT, intDate, intTotalAmount, strKEY):
        """
        Inicializamos la Clase estableciendo sus Propiedades Privadas.
        """
        # Propiedades Privadas
        self.AuthNumber = strAuthNumber
        self.InvoiceNumber = intInvoiceNumber
        self.ClientNIT = intClientNIT
        self.Date = intDate
        self.TotalAmount = intTotalAmount
        self.Key = strKEY
        self.Verhoeff = {}

        # Adicionamos un atributo para saber que version de algoritmo de impuestos se esta usando
        self.version = 'V1-6'

        # Diccionar de de 64 caracteres para la logica del obtener el Base64 de Impuestos
        self.Dictionary64 = { 0: '0', 1: '1', 2: '2', 3: '3', 4: '4', 5: '5',
                              6: '6', 7: '7', 8: '8', 9: '9', 10: 'A', 11: 'B',
                              12: 'C', 13: 'D', 14: 'E', 15: 'F', 16: 'G', 17: 'H',
                              18: 'I', 19: 'J', 20: 'K', 21: 'L', 22: 'M', 23: 'N',
                              24: 'O', 25: 'P', 26: 'Q', 27: 'R', 28: 'S', 29: 'T',
                              30: 'U', 31: 'V', 32: 'W', 33: 'X', 34: 'Y', 35: 'Z',
                              36: 'a', 37: 'b', 38: 'c', 39: 'd', 40: 'e', 41: 'f',
                              42: 'g', 43: 'h', 44: 'i', 45: 'j', 46: 'k', 47: 'l',
                              48: 'm', 49: 'n', 50: 'o', 51: 'p', 52: 'q', 53: 'r',
                              54: 's', 55: 't', 56: 'u', 57: 'v', 58: 'w', 59: 'x',
                              60: 'y', 61: 'z', 62: '+', 63: '/'
                            }

    # Funciones Publicas
    def get_test(self):
        return "TEST de BolTransaction"

    def get_control_code(self):
        """
        Generar y Obtener el codigo de control en base a una determinada transaccion.
        """

        # Establecemos el diccionario de digitos verificadores
        self.Verhoeff = self._get_verhoeff_dictionary()
        # if request.debug:
        #     print "K32 self.Verhoeff", self.Verhoeff

        # Obtenemos el TOTAL de la suma aritmetica
        sumArit = self._get_dictionary_sum_total()
        # if request.debug:
        #     print "K32 sumArit", sumArit

        # Obtenemos el Mod 64 de la suma aritmetica
        mod64 = self._get_modulo_operator(sumArit)
        # if request.debug:
        #     print "K32 mod64", mod64

        # Obtene el valor Base64
        base64 = self._get_base64(mod64)
        # if request.debug:
        #     print "K32 base64", base64

        # Ciframos el Base64 para obtener asi el codigo de control en valor hexadecimal
        strControlCode = self._get_encryptAndFormat_ControlCode(base64)
        # if request.debug:
        #     print "K32 strControlCode", strControlCode

        return strControlCode

    # Funciones Privadas
    def _get_verhoeff_dictionary(self):
        """
        Obtenemos un diccionario con los digitos verificadores usando el algoritmo de Verhoeff.
        PASO 2 (VERHOEFF)
        """
        return  { 'auth_nro': self._add_verhoeff_digit(self.AuthNumber),
                  'invoice_nro': self._add_verhoeff_digit(self.InvoiceNumber),
                  'nit': self._add_verhoeff_digit(self.ClientNIT),
                  'date': self._add_verhoeff_digit(self.Date),
                  'amount': self._add_verhoeff_digit(self.TotalAmount)
                }

    def _add_verhoeff_digit(self, value):
        """
        Adiciona el digito verificador y retorna un valor entero.
        Por ejemplo, para un valor que representa el numero de factura 1503, el digito verificador verhoeff seria 1 y el valor a retornar seria 15031
        NOTA.- Ya no transformamos a INT el value ni la respuesta, xq si el NIT es 0 por ejemplo, el digito verhoeff seria 4
        Transformando a entero la respuesta es 4, mientras que sin transformar la respuesta es 04
        si volvemos a ejecutar el verhoeff para 4 y 04 la respuesta seria 43 y 047 respectivamente.
        """
        # YA NO TRANSFORMAMOS A ENTERO LOS VALORES...
        # Primero transformamos el value en entero
        # intValue = int(value)
        intValue = value

        # obtenemos el digito verificador
        strValue = verhoeff.calc_check_digit(intValue)

        # Concatenamos
        strValue = '%s%s' % (intValue, strValue)

        # YA NO TRANSFORMAMOS A ENTERO LA RESPUESTA
        # Retornamos el valor como entero
        # return int(strValue)
        return strValue

    def _get_dictionary_sum_total(self):
        """
        Suma los valores enteros del diccionario Verhoeff obtenido
        PASO 3 (Suma Aritmetica)
        """
        # return sum(self.Verhoeff.values())
        # Ahora los Nro. concatenados con VERHOEFF son string por si el nro. de NIT es 0, se obtiene el valor 04 y no 4 que es cuando se transformaba a enteros.
        return sum(int(x) for x in self.Verhoeff.values())

    def _get_modulo_operator(self, intValue):
        """
        Obtener el mod o module operator o Modulus ( es decir, lo que sobra de una determinada division)
        Para el SIN (BOLIVIA) se debe calcular el intValue Mod ((64^5) -1).
        PASO 4 (MOD)
        """
        return intValue % (pow(64, 5) - 1)

    def _get_base64(self, intValue):
        """
        Obtener el valor Base64 en base al diccionario de 64 bits y logica de division entre 64.
        NOTA. esta logica es muy distinta a usar el metodo import base64; base64.b64encode(intValue)
        PASO 5 (Base64)
        """
        boolContinue = True
        intCociente = 0
        intResto = 0
        strCode = ''
        intNum = intValue

        while boolContinue:

            # Dividimos el intNum entre 64 y obtenemos solamente la parte entera, es decir sin decimales, y si REDONDEO
            # para ellos usamos la funcion int()
            intCociente = int(intNum / 64)
            # if request.debug:
            #     print "K32 intCociente", intCociente

            # Obtenemos el RESTO o Mod de la misma division entre 64
            intResto = intNum % 64
            # if request.debug:
            #     print "K32 intResto", intResto

            # Concatenamos hacia la IZQUIERDA el Codigo BASE 64, usando como el KEY el valor intResto (mod 64)
            strCode = '%s%s' % (self.Dictionary64[intResto], strCode)
            # if request.debug:
            #     print "K32 strCode", strCode

            boolContinue = intCociente > 0
            # if request.debug:
            #     print "K32 boolContinue", boolContinue

            # ahora el numero es el cociente para continuar el loop y no entrar en un ciclo infinito
            intNum = intCociente

            # if request.debug:
            #     print "K32 *****************************"

        # retornamos el strCode generado haciendo el TRIM o quitando espacios en blanco (segun la logica no deberia existir, pero talvez despues hay algun cambio o algo asi.)
        return strCode.strip()

    def _get_encryptAndFormat_ControlCode(self, strValue):
        """
        Encriptamos o Ciframos un valor usando utilizando el algoritmo Alleged RC4, la llave de dosificacion y codificacion Hexadecimal.
        Ejemplo: usando la llave 'SeSaMo', el strValue = '++W+G' deberiamos obtener el valor : C4-3B-93-A8-25
        PASO 6 (Cifrar)
        """

        # Primero Ciframos el VALOR usando el algoritmo AllegedRC4
        strMsg = self._get_AllegedRC4_with_key(strValue, self.Key)

        # if request.debug:
        #     print "K32 strMsg", strMsg

        # Transformamos a valores Hexadecimales y en mayusculas
        strHex = self._to_hexadecimal(strMsg)
        # if request.debug:
        #     print "K32 strHex", strHex

        return self._get_format_control_code(strHex)

    def _to_hexadecimal(self, strValue):
        """
        Codifica una cadena a su respectivo valor Hexadecimal y en mayusculas
        HEX : 1,2,3,4,5,6,7,8,9,0,A,B,C,D,E,F
        """

        return strValue.encode('hex').upper()

    def _get_AllegedRC4_with_key(self, strValue, strKey):
        """
        Encriptamos o Ciframos un valor usando utilizando el algoritmo Alleged RC4, utilizando una llave especifica.
        """
        # creamos una instancia al objeto del algoritmo ARC4 con la llave de dosificacion.
        objCipher = ARC4.new(strKey)
        # if request.debug:
        #     print "K32 strKey", strKey

        # Ciframos en valor
        strMsg = objCipher.encrypt(strValue)

        return strMsg

    def _get_format_control_code(self, strEncryptHex):
        """
        Formatea una cadena de texto que representa un valor cifrado, con solo datos Hexadecimales siguiendo todos los pasos de la logica requerida por impuestos
        para que al final se muestre con formato A1-B2-C3-D4.
        Es decir un string con valores en mayusculas con PAR de datos separados por guiones
        HEX : 1,2,3,4,5,6,7,8,9,0,A,B,C,D,E,F
        """

        # obtenemos un array cada 2 caracteres usando regular expression (re)
        arr = re.findall('..?', strEncryptHex)
        # if request.debug:
        #     print "K32 arr", arr

        # hacemos un JOIN del array de cada 2 caracteres para separarlo con el signo '-'
        return '-'.join(arr)


# Al Intentar Validar el aplicativo nos dimos cuenta que el algoritmo o pasos que usamos en la version V1 quedo obsoleto, por tanto ahora se debe usar la version V7
# Para ello creamos una clase que extiende el BolTransaction que es la version 1
class BolTransactionV7(BolTransaction):
    """
    Clase que representa una transaccion de factura con normativa Boliviana para poder generar un codigo de verificacion.
    http://www.impuestos.gob.bo/index.php?option=com_content&view=article&id=1564&Itemid=584
    http://www.impuestos.gob.bo/images/GACCT/FACTURACION/CodigoControlV7.pdf
    VERSION 7
    PASO 1 (INICIALIZAMOS los valores)
    EJEMPLO: usando datos: AuthNumber : 29040011007, ProportionKey: 9rCB7Sv4X29d)5k7N%3ab89p-3(5[A
    EJEMPLO SIN : AuthNumber: 29010915579, ProportionKey:SeSaMo, InvoiceNumer: 1503, fecha; 20070702, NIT: 4189179011, monto: 2500
    CODIGO DE CONTROL :  6A-DC-53-05-14
    """

     # Inicializacion de la clase
    def __init__(self, strAuthNumber, intInvoiceNumber, intClientNIT, intDate, intTotalAmount, strKEY):
        """
        Inicializamos la Clase estableciendo sus Propiedades Privadas.
        """
        # Inicializamos la BASE
        # BolTransaction.__init__(self, strAuthNumber, intInvoiceNumber, intClientNIT, intDate, intTotalAmount, strKEY)
        # New python Style
        # super(BolTransactionV7, self).__init__(strAuthNumber, intInvoiceNumber, intClientNIT, intDate, intTotalAmount, strKEY)
        super(self.__class__, self).__init__(strAuthNumber, intInvoiceNumber, intClientNIT, intDate, intTotalAmount, strKEY)
        # Como extension debemos modificar el atributo version, para saber que version de algoritmo de impuestos se esta usando
        self.version = 'V7'

    # Sobreescribimos la funcionalidad de get_control_code para hacer los pasos segun la version 7
    def get_control_code(self):
        """
        Generar y Obtener el codigo de control en base a una determinada transaccion.
        Tratamos de modulizar o generar funciones para cada paso, de manera que despues se pueda extender o sobreescribir estas si es necesario.
        """

        # if request.debug:
        #     print "K32 BolTransactionV7 -> get_control_code"

        # if request.debug:
        #     print "K32 self.ClientNIT", self.ClientNIT
        #     print "K32 self.ClientNIT VERHOEFF", self._add_n_verhoeff_digits(2, self.ClientNIT)

        # Establecemos el diccionario de digitos verificadores
        self.Verhoeff = self._get_verhoeff_dictionary()
        # if request.debug:
        #     print "K32 self.Verhoeff", self.Verhoeff

        # Obtenemos el TOTAL de la suma aritmetica
        sumArit = self._get_dictionary_sum_total()
        # if request.debug:
        #     print "K32 sumArit", sumArit

        # Adicionamos 5 Digitos verificadores a la suma aritmetica del diccionario.
        sumArit5 = self._add_n_verhoeff_digits(5, sumArit)
        # if request.debug:
        #     print "K32 sumArit5", sumArit5

        # Obtenemos los ultimos 5 digitos de sumArit5, es decir los 5 digitos verificadores
        digts5 = str(sumArit5)[-5:]

        # Obtenemos las 5 Cadenas a utilizar segun los 5 digitos veificadores.
        arrCadenas = self._get_string_array_from_key(digts5)

        # Generamos una cadena que concatena NroAuth+Arr[0]+NroFactura+Arr[1]+Nit+Arry[2]+Fecha+Arr[3]+Monto+Arry[4]
        strConcatenate = self._concatenate_values_with_array(arrCadenas)

        # if request.debug:
        #     print "K32 _concatenate_values_with_array -> strConcatenate", strConcatenate

        # Generamos la llave para cifrar
        # en esta version V7 de impuestos, se debe concatenar a la llave el valor de digts5
        strKeyForEncryp = "%s%s" % (self.Key, digts5)

        # Ciframos la candena concatenada con llave para encriptar.
        strEncrypt = self._get_AllegedRC4_with_key(strConcatenate, strKeyForEncryp)

        # if request.debug:
        #     print "K32 _get_AllegedRC4_with_key(strConcatenate) -> strEncrypt", strEncrypt

        # Transformamos a HEXADECIMAL el valor CIFRADO
        strEncryptHex = self._to_hexadecimal(strEncrypt)

        # if request.debug:
        #     print "K32 strEncryptHex (concatenado)", strEncryptHex

        # Obtenemos un Diccionario de suma total y sumas parciales segun logica de impuestos en base al valor cifrado
        dicSumas = self._get_dictionary_sum_ascii(strEncryptHex)

        # Obtener la suma aritmetica del diccionario de sumas, bajo la logica de impuestos.
        # es decir usando dividendos en base a digts5
        totalSumas = self._get_sum_dividendos(dicSumas, digts5)

        # Obtene el valor Base64
        # if request.debug:
        #     print "K32 _get_base64 -> totalSumas", totalSumas
        base64 = self._get_base64(totalSumas)

        # if request.debug:
        #     print "++++++K32 _get_base64++++++"

        # Ciframos el BASE64 usando la llave strKeyForEncryp
        strEncrypt = self._get_AllegedRC4_with_key(base64, strKeyForEncryp)

        # if request.debug:
        #     print "K32 _get_AllegedRC4_with_key(base64) -> strEncrypt", strEncrypt

        # Transformamos a HEXADECIMAL el valor CIFRADO
        strEncryptHex = self._to_hexadecimal(strEncrypt)

        # if request.debug:
        #     print "K32 strEncryptHex (base64)", strEncryptHex

        # if request.debug:
        #     print "********** K32 BolTransactionV7 -> get_control_code FIN **********"

        return self._get_format_control_code(strEncryptHex)

    # Funciones Privadas

    # Extender el metodo de la BASE xq ahora debemos adicionar 2 digitos verificadores.
    # y el diccionario de respuesta es de 4 items en lugar de 5.
    def _get_verhoeff_dictionary(self):
        """
        Obtenemos un diccionario con los digitos verificadores usando el algoritmo de Verhoeff.
        PASO 2 (VERHOEFF)
        """

        # **************
        # Obtenemos el Diccionario de la BASE que tiene 5 items y 1 solo digito verificador.
        # dicBase = super(BolTransactionV7, self)._get_verhoeff_dictionary()

        # # Obtenemos un nuevo diccionario, pero adicionando un digito mas a cada elemento del dicBase
        # return  { 'auth_nro': self._add_verhoeff_digit(dicBase['auth_nro']),
        #           'invoice_nro': self._add_verhoeff_digit(dicBase['invoice_nro']),
        #           'nit': self._add_verhoeff_digit(dicBase['nit']),
        #           'date': self._add_verhoeff_digit(dicBase['date']),
        #           'amount': self._add_verhoeff_digit(dicBase['amount'])
        #         }
        # ************

        # En lugar de obtener un diccionario con la funcionalidad BASE y despues volver a correr el add_verhoeff_digits,
        # simplemente ahora usamos la funcionalidad _add_n_verhoeff_digits y generarmos un solo diccionario
        return  { 'auth_nro': self._add_n_verhoeff_digits(2, self.AuthNumber),
                  'invoice_nro': self._add_n_verhoeff_digits(2, self.InvoiceNumber),
                  'nit': self._add_n_verhoeff_digits(2, self.ClientNIT),
                  'date': self._add_n_verhoeff_digits(2, self.Date),
                  'amount': self._add_n_verhoeff_digits(2, self.TotalAmount)
                }

    # Extender el metodo de la BASE xq ahora debemos cifrar con una llave en base al KEY y 5DigitosVerificadores
    # Es decir el strVALUE ya tiene el valor cifrado.
    def _get_encryptAndFormat_ControlCode(self, strValue):
        """
        Encriptamos o Ciframos un valor usando utilizando el algoritmo Alleged RC4, la llave de dosificacion y codificacion Hexadecimal.
        Ejemplo: usando la llave 'SeSaMo', el strValue = '++W+G' deberiamos obtener el valor : C4-3B-93-A8-25
        PASO 6 (Cifrar)
        """

        # Transformamos a valores Hexadecimales y en mayusculas...?
        strHex = self._to_hexadecimal(strMsg)
        # if request.debug:
        #     print "K32 strHex", strHex

        return self._get_format_control_code(strHex)

    def _add_n_verhoeff_digits(self, n, value):
        """
        Adicionar una cantidad de N digitos verificadores verhoeff.
        Es decir correr N veces _add_verhoeff_digit concatenando el valor para generer el siguiente digito verificador.
        """

        strResp = value

        for i in range(0, n):
            # Adicionamos el digito verificador al value y lo colocamos a la variable para que cada loop el value tenga los digitos al final.
            strResp = self._add_verhoeff_digit(strResp)

        return strResp

    def _get_string_array_from_key(self, digts5):
        """
        Obtener un array de longitud 5, es decir 5 cadenas de la LLAVE de dosificacion en base a los 5 Digitos verificadores (sumatoria diccionario Verhoeff con loop 5)
        Segun la Logica de Impuestos, a los 5 digitos verificadores a cada digito se le suma 1 y el valor resultante es la longintud de caracteres a usar del KEY o llave de dosificacion por cada cadena.
        Ejemplo: si tenemos digts5: 71621 y Llave : 9rCB7Sv4X29d)5k7N%3ab89p-3(5[A
        ARRAY respuesta : ('9rCB7Sv4', 'X2', '9d)5k7N', '%3a', 'b8')
        """
        arrResp = []

        # copiamos el valor de llave
        # Tomar en cuenta que si llave es corta o es un string empty, no hay problema xq usamos [:] para obtener por posicion y longitud carateres, si es vacio retorna vacio, y si es corta obtiene la cantidad que puede segun el size de la llave.
        aux_key = self.Key

        # Recorremos cada digito que se ditiene en digts5 (deberian ser 5 digitos)
        for digit in map(int, str(digts5)):
            # Al digito se le suma 1 y se tiene la longitud que se tiene que usar de la cadena que representa la llave de dosificacion
            key_len = digit + 1
            # Obtenemos del string CADENA , desde el Inicio : hasta la longitud que se indica en key_len
            strCadena = aux_key[:key_len]
            # Quitamos de aux_key el pedazo de cadena usado o agregado a strCadena.
            # Es decir hace al reves del strCadena, obtenemos el string desde el ultimo adicionado a strCadena hacia el final de la cadena
            # y lo establecemos como nuevo valor de aux_key
            aux_key = aux_key[key_len:]
            # Adicionamos el strCadena al Array de respuesta.
            arrResp.append(strCadena)

        # if request.debug:
        #     print "K32 _get_string_array_from_key -> arrResp", arrResp

        return arrResp

    #  Extender el metodo de la BASE se suma pero no se toma en cuenta el valor del key auth_nro
    def _get_dictionary_sum_total(self):
        """
        Suma los valores enteros del diccionario Verhoeff obtenido
        PASO 3 - (Suma Aritmetica)
        NOTA.- Tomar en cuenta q en la suma no se debe tomar en cuenta el KEY auth_nro
        """

        # return sum(self.Verhoeff.values())
        # Ahora los Nro. concatenados con VERHOEFF son string por si el nro. de NIT es 0, se obtiene el valor 047 y no 43 que es cuando se transformaba a enteros.
        return sum(int(i[1]) for i in self.Verhoeff.iteritems() if i[0] != 'auth_nro')

    def _concatenate_values_with_array(self, arr):
        """
        Generamos una cadena que concatena NroAuth+Arr[0]+NroFactura+2Verhoeff+Arr[1]+Nit+2Verhoeff+Arry[2]+Fecha+2Verhoeff+Arr[3]+Monto+2Verhoeff+Arry[4]
        PASO 4
        """
        return "%s%s%s%s%s%s%s%s%s%s" % (self.AuthNumber, arr[0],
                                         self.Verhoeff['invoice_nro'], arr[1],
                                         self.Verhoeff['nit'], arr[2],
                                         self.Verhoeff['date'], arr[3],
                                         self.Verhoeff['amount'], arr[4]
                                        )
    def _get_sum_ascii_values(self, strValue):
        """
        Obtiene la suma de los valores ASCII de un determinado STRING.
        Para OBTENER el valor ascii de un char , usamos la funcion ord() de python
        Podriamos hacer un for normal:
        for ch in strValue:
            code = ord(cd)
        pero para ser mas python, usamos map para ya generar un iterador con cada ASCII value de cada character que hay en strValue
        for code in map(ord, strValue):
            sum +=code
        ahora usamos la funcion sum() para hacer todo en una sola linea.
        """
        # Usamos MAP para generar un iterador o list de valores INT q representan el valor asci
        # y al final retornamos la suma

        return sum(ascii for ascii in map(ord, strValue))

    def _get_dictionary_sum_ascii(self, strValue, intSumPositonsBy=5):
        """
        Obtenemos un Dicciionario con suma total y parciales (ciertos Rangos), segun lo que indica Impuestos.
        Ejemplo con la cadena cifrada strValue: 69DD0A42536C9900C4AE6484726C122ABDBF95D80A4BA403FB7834B3EC2A88595E2149A3D965923BA4547B42B9528AAE7B8CFB9996BA2B58516913057C9D791B6B748A
        Sumatoria Total: ST = 7720
        Sumatoria Parcial 1 (Posiciones 1-6-11-16-21...): SP1 = 1548 => calculando el string seria 6A60622F04738EA5AB5EF659797
        Sumatoria Parcial 2 (Posiciones 2-7-12-17-22...): SP2 = 1537 => calculando el string seria 94CC46A9A08E82394427BB81C14
        Sumatoria Parcial 3 (Posiciones 3-8-13-18-23...): SP3 = 1540
        Sumatoria Parcial 4 (Posiciones 4-9-14-19-24...): SP4 = 1565
        Sumatoria Parcial 5 (Posiciones 5-10-15-20-25..): SP5 = 1530

        Por tanto, vemos que se debe ir sumando 5 a cada posicion, por defaulr intSumPositonsBy=5

        Tomar en cuenta que IMPUESTOS indica posicion 1,6,11, pero en array seria 0,5,10,15,20....
        Decir Primera posicion 1 en un array es el valor en el indice 0
        por lo tanto debemos distinguir esa denominacion
        """
        dicRes = {'ST': self._get_sum_ascii_values(strValue)}

        lenValue = len(strValue)

        # Se debe hacer un Loop de 5 (1,2,3,4,5) y cada uno de estos ir sumando 5 para tener las posiciones 1,6,11,16,21,26,31,36,41....... | 2,7,12,17,22,27,32,37,42,47....
        for i in range(0, 5):
            # Verificamos si 'i' es decir el indice del range no sea mayor o igual a la longitud del string
            if i >= lenValue:
                # Salimos del FOR xq no nos sirve ir intentanto procesar un texto que no puede manejar los otros loops que son el inicio para generar los subtextos o cadenas
                # strValue puede ser de longitud 1 asi retornamos la Suma Total y una Suma Parcial
                break

            # Usamos 2 variables para distinguir posicion e indice
            # Iniciamos el Index en base al loop range de 5 (0,1,2,3,4)
            intIndex = i
            # Iniciamos la posicion en base index + 1
            intPosition = intIndex + 1

            # Agregamos en un array los index para ayudarno s debuguear
            arrIndex = []
            arrIndex.append(intIndex)

            # Agregamos en una cadena auxiliar los valores segun la posicion que indica impuestos.
            # Inicilizamos esta cadena con el primer valor en base al intIndex que esta iniciado segun el LOOP
            strAux = str(strValue[intIndex])

            # Empezar e ir sumando intSumPositonsBy (5) hasta que no sea mayor o igual a longitud de strValue
            # xq usamos indices al manejar arrays
            while intIndex + intSumPositonsBy < lenValue:
                # sumamos 5 posiciones
                intIndex += intSumPositonsBy
                # Adicionamos el indice al array
                arrIndex.append(intIndex)
                # concatenamos el valor que hay en strValue en intIndex
                strAux += str(strValue[intIndex])

            # if request.debug:
            #     print "K32 _get_dictionary_sum_ascii -> arrIndex", arrIndex
            #     # mostramos el array pero con posiciones segun impuestos ( es decir sumamos +1 a cada index)
            #     # tb podriamos mostrar un string con comas como separador
            #     # print ','.join(str(i) for i in  map(lambda x: x+1,a))
            #     # o ', '.join(str(x) for x in list)
            #     print "K32 _get_dictionary_sum_ascii -> posiciones Impuestos", map(lambda x: x+1, arrIndex)

            # Obtenemos la sumatoria ascii de los valores que se tienen en las posiciones obtenidas.
            # y lo adicionamos al Diccionario, adicionando un KEY SP (suma Parcial) & N (posicion)
            dicRes["SP%i" % intPosition] = self._get_sum_ascii_values(strAux)

        # if request.debug:
        #     print "K32 _get_dictionary_sum_ascii -> dicRes", dicRes

        return dicRes

    def _get_sum_dividendos(self, dicSum, digts5):
        """
        Obtener la suma aritmetica de todas las sumas parciales multiplicadas por la suma total (valores del diccionario de sumas) y divididas (usando solo la parte entera truncar o truncate) entre cada digito verhoeff digts5 + 1

        La Lógica de impuestos:

        5 Dígitos Verhoeff: 71621
        Dividendos: 8-2-7-3-2 (Suma 1 a cada dígito Verhoeff)
            ST * SP1 = 7720 * 1548 = 11950560 -> Truncar(11950560 / 8) = 1493820
            ST * SP2 = 7720 * 1537 = 11865640 -> Truncar(11865640 / 2) = 5932820
            ST * SP3 = 7720 * 1540 = 11888800 -> Truncar(11888800 / 7) = 1698400
            ST * SP4 = 7720 * 1565 = 12081800 -> Truncar(12081800 / 3) = 4027266
            ST * SP5 = 7720 * 1530 = 11811600 -> Truncar(11811600 / 2) = 5905800
                                                            SUMA TOTAL : 19058106

        TRUNCAR : usar solamente la parte ENTERA del resultado de una division
            num = num
            truncar(num) => 3

            En python transformando a INT un valor decimal, basicamente hace estos
            print int(num) => 3
            o tambien podemos hacer:
            print math.trunc(num) =>3

            Esto es distinto a decirle ROUND con 0 decimales
            int(round(num)) => 3, pero si num = 3.51, el resultado seria => 4
        """

        # Tomar en cuenta q el diccionario de sumas, puede contener 1,2,3,4 o 5 Sumas Parciales dependiendo el size de valor que se uso para calcular estas sumas
        # pero siempre deberia tener la SUMA TOTAL y por lo menos una SUMA PARCIAL xq el valor usado para calcular las sumas no puede ser VACIO.

        # Primero obtenemos el valor de la suma total del diccionario
        ST = dicSum['ST']

        # ahora vamos multiplicando cada SUMA PARCIAL y dividiendola entre el digito correspondiente +1 de los digits5 (verhoeff)
        # Usamos un contador para saber en que Suma Parcial estamos.
        intContador = 1
        # Recorremos cada digito que se ditiene en digts5 (deberian ser 5 digitos)
        for digit in map(int, str(digts5)):
            # Tomar en cuenta que no todos los digitos podrian no tener su correspondiente suma parcial
            # esto depende del size del string cifrado usado para generar el diccionario de sumas parciales.
            intDividendo = digit + 1
            strKEY = "SP%i" % intContador
            strTotalKey = "TP%i" % intContador

            # Verificamos si tenemos el KEY strKEY
            if strKEY in dicSum:
                # Calculamos el TOTAL = int((ST * SP<strKEY>) / intDividendo)
                total = int((ST * dicSum[strKEY]) / intDividendo)
                # adicionamos al Diccionario un nuevo KEY de total para que despues sumemos todos los que empiecen con TOTAL (T)
                dicSum[strTotalKey] = total

            # Aumentamos el Contador
            intContador += 1

        # Retornamos la suma aritmetica de todos los TOTALES PARCIALES
        # para ello cada item del diccionario [0] => key [1] => value tenemos que sumar solamente los valores donde su KEY empiece con T
        # i[1] nos retorna el valor del item que se itera
        # i[0] nos retorna el KEY del item que se itera
        # i[0][0] nos retorna el primer caracter del KEY del item que se itera.
        # TOmar en cuenta q SUM retorna 0 si no hay ningun valor q su KEY matchee con el IF

        # if request.debug:
        #     print "K32 _get_sum_dividendos -> dicSum", dicSum

        return sum(i[1] for i in dicSum.iteritems() if i[0][0] == 'T')
