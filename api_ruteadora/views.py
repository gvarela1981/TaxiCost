
"""
.. module:: views
   :platform: Unix, Windows
   :synopsis: Un modulo utilizable.

.. moduleauthor:: Mi Nombre <scastellano10@gmail.com>


"""


from django.http import JsonResponse
import requests
from django.shortcuts import render
#from modules.modules2.parametros import constantes
from django.conf import settings
# para implementar la vista de idex
from django.http import HttpResponse
from api_ruteadora.models import Endpoint, Costo, Ruteo

import json as simplejson
# from commons.commons import aplicar_callback
# from commons.commons import armarEstructuraGeoLayer
from django.contrib.gis.geos import GEOSGeometry

#APIs que se consumen, despues de actualizarlas se debe reiniciar servicio
#Server de ruteo
objRuteo = Endpoint.objects.filter(nombre='Ruteo')
server = objRuteo.values_list('url', flat=True).first()
#server datos utiles
objRuteo = Endpoint.objects.filter(nombre='Destino en CABA')
server_datos_utiles = objRuteo.values_list('url', flat=True).first()
#Server autopista
objRuteo = Endpoint.objects.filter(nombre='Filtro de Autopista')
server_no_autopista = objRuteo.values_list('url', flat=True).first()
#Server de retorno a caba
objRuteo = Endpoint.objects.filter(nombre='Retorno a CABA')
server_retorno_caba = objRuteo.values_list('url', flat=True).first()

MAX_POINTS = settings.MAX_POINTS if hasattr(settings, 'MAX_POINTS') else 0
objSettings = Costo.objects.filter(nombre='Costo')
INICIO_SERVICIO_DIURNO = objSettings.values_list('INICIO_SERVICIO_DIURNO', flat=True).first()
INICIO_SERVICIO_NOCTURNO = objSettings.values_list('INICIO_SERVICIO_NOCTURNO', flat=True).first()
BAJADA_BANDERA_DIURNA = objSettings.values_list('BAJADA_BANDERA_DIURNA', flat=True).first()
BAJADA_BANDERA_NOCTURNA = objSettings.values_list('BAJADA_BANDERA_NOCTURNA', flat=True).first()
VALOR_FICHA_DIURNA = objSettings.values_list('VALOR_FICHA_DIURNA', flat=True).first()
VALOR_FICHA_NOCTURNA = objSettings.values_list('VALOR_FICHA_NOCTURNA', flat=True).first()
PORCENTAJE_DIURNO_AJUSTE = objSettings.values_list('PORCENTAJE_DIURNO_AJUSTE', flat=True).first()
PORCENTAJE_NOCTURNO_AJUSTE = objSettings.values_list('PORCENTAJE_NOCTURNO_AJUSTE', flat=True).first()

# index

def index(request):
    return HttpResponse("Hello, world. You're at the polls index.")

#render swagger de mapa de puntos taxi
def puntosmapa_sw(request):
    return render(request, 'ingresopuntos/puntosmapassw.html', {})
#Puntos de la busqueda
def ingresarPuntosMapa(request):
    """Funcion que randeriza el frontend para ingreso de puntos en leaflet y envio ajax hacia
    la url calculo_ruta->consultarPuntos. Es llamada desde el ruteador con la url puntosMapas.

    Args:
        ``request`` :  Sin uso.


    Returns:
        render html.
        """
    return render(request, 'ingresopuntos/index2.html', {})
def ingresarPuntos(request):
    #return JsonResponse({'santi': 'ssssss'})
    return render(request, 'ingresopuntos/ingresopuntos.html', {})

def validarPuntos(puntos, headers):
    locValidado = []
    for i in puntos:
        url = server_no_autopista + i[1] + ',' + i[0] + '?exclude=motorway'

        response = requests.request('GET', url, headers=headers, allow_redirects=False)

        resultado_du = response.json()
        # print('resultado json:  ' + str(resultado_du))
        punto_chequeado = resultado_du['waypoints'][0]['location']
        # un array con 3 strs, dos de lat lon y una ultima con lat,lon, todos habienso sido chequeados
        punto = [str(punto_chequeado[1]), str(punto_chequeado[0]),
                 str(punto_chequeado[1]) + ',' + str(punto_chequeado[0])]

        locValidado.append(punto)
    return locValidado

def armarRespuestaPuntos(datos,gml):
    """Funcion que es llamada internamente y que arma diversas consultas a APIs externas
    para realizar el calculo de una traza definida por los puntos contenidos en datos.

    Args:
        ``datos (array)``:  Coleccion de flotantes que representan los pares ordenados lat lon
        que serviran para la realización de la traza. No puede contener menos
        de cuatro numeros, ni una cantidad impar, esta verificacion se hace
        en la funcion llamadora.

        ``gml (int)`` : Entero (0,1) que determina si en el json de salida se agrega o no la traza
        calculada entregada por el server de ruteo en formato gml.
    Returns:
            ``json``
        """
    
    n = 2
    # divido los datos en pares ordenados de coordenadas
    puntos = list(zip(*[iter(datos)] * n))
    
    headers = {
        'Content-Type': 'application/json'
    }

    # valido los puntos ingresados
    loc = validarPuntos(puntos, headers)
    destino = loc[-1]

    response = getRuteo(loc, headers)
    resultado = response.json()
    try:
        total_time = resultado['route_summary']['total_time']
        total_distance = resultado['route_summary']['total_distance']
    except Exception as e:
        print ('consulta rechazada en el server de ruteo: '+str(e))

    # Verificar si esta dentro o fuera de CABA el ultimo punto
    # si el ultimo punto esta fuera de caba se calcula el retorno
    destinoInCABA = destinoIsInCaba(destino, headers)
    print("destinoInCABA es", destinoInCABA)

    if (destinoInCABA is False):

        # Consultar punto de retorno a CABA
        response = getRetornoCABA(destino, headers)
        
        resultado_du = response.json() # metodo original
        #resultado_du = response # metodo nuevo
                
        # Formateando el punto de retornoCABA para el ruteo
        retornoCABA = (resultado_du[0]['latitud'], resultado_du[0]['longitud'])
        ruteoRetornoCABA = [destino]
        # ruteoRetornoCABA.append(retornoCABA)
        ruteoRetornoCABA.append([retornoCABA[0], retornoCABA[1], str(retornoCABA[0] + "," + retornoCABA[1])])
        
        print('debaguear')

        response = getRuteo(ruteoRetornoCABA, headers)
        print('respuesta recibida')
        resultado = response.json()
        print('resultado gml')
        retorno_caba_distance = resultado['route_summary']['total_distance']
        retorno_caba_time = resultado['route_summary']['total_time']

    #el punto final esta dentro de caba
    else:
        retorno_caba_time = 0
        retorno_caba_distance = 0

    resultado_json = {}

    resultado_json["total_time"] = total_time
    resultado_json["total_distance"] = total_distance
    resultado_json["return_caba_time"] = retorno_caba_time
    resultado_json["return_caba_distance"] = retorno_caba_distance
    resultado_json["INICIO_SERVICIO_DIURNO"] = INICIO_SERVICIO_DIURNO
    resultado_json["BAJADA_BANDERA_DIURNA"] = BAJADA_BANDERA_DIURNA
    resultado_json["VALOR_FICHA_DIURNA"] = VALOR_FICHA_DIURNA
    if gml=='1':
        resultado_json["gml"] = resultado

    resul = resultado_json
    print(resul)

    return JsonResponse(resul)

def consultarPuntos(request):
    """Funcion que es llamada desde el ruteador con la url calculo_ruta. Filtra y analiza el contenido
    del request para que la llamada a los servidores de ruteo sea consistente.

    Args:
        ``request (array)``:  request que puede contener el verbo POST o GET, que es una coleccion
        de flotantes. Condicion: no puede contener menos de 4 parametros, ni mas de ``MAX_POINTS``.

        ``gml (int)`` : Entero (0,1) que determina si en el json de salida se agrega o no la traza
        calculada entregada por el server de ruteo en formato gml.

    Returns:
            ``json``
    """
    resultado_json = {}

    if (request.POST):
        #incluir el header crsf en la llamada ajax
        datos = request.POST.getlist('data[]')
        gml = request.POST.get('gml')
    else:
        datos = request.GET.getlist('data[]')
        gml = request.GET.get('gml')
    print('datos')
    print(len(datos))
    print(int(len(datos)/2))
    # este filtrado tambien contempla la posibilidad de que no se utilice el nombre de lista data[] en algun parametro
    # esta oriendado a un uso inadecuado por get desde el cgi
    if (len(datos) < 4):
        resultado_json["error"] = 'La llamada necesita al menos 2 coordenadas lat lon. Ej: http://$host/calculo_ruta?data[]=lat1&data[]=lon1&data[]=lat2&data[]=lon2&data[]=lat3&data[]=lon3&data[]=lat4&data[]=lon4&gml=1'
        resul = resultado_json
        return JsonResponse(resul)
    else:
        #mas de 2 coordenadas pero faltando un parametro, lat o lon
        if (len(datos)%2 != 0):
            resultado_json["error"] = 'La llamada no contiene una cantidad adecuada de pares ordenados'
            resul = resultado_json
            return JsonResponse(resul)
        else:
            # este error debe ser filtrado en el frontend especifico de este proyecto, ya que los demas errores
            # de coordenadas no podrian presentarse en el caso de la definicion de puntos por drawtool leaflet
            if (len(datos) / 2 > MAX_POINTS):
                resultado_json["error"] = 'No ingrese mas de 10 puntos'
                resul = resultado_json
                return JsonResponse(resul)
            else:
                #gml = True
                print('gmll crudo')
                print(gml)
                res = armarRespuestaPuntos(datos,gml)
                return res
    #else:
      #  resultado_json["error"] = 'Error en el request'
      #  resul = resultado_json
      #  return JsonResponse(resul)

def prepararMensajeRuteo(loc):
    """
    Prepara el string para la consulta del ruteo
    """
    mensaje ='?output=json'
    j = 0
    for i in loc:
        if j < len(loc):
            mensaje = mensaje + '&loc=' + loc[j][2]
        j = j + 1
        # linea original de armado
        # mensaje = '?output=json&loc=' + loc[0][2] + '&loc=' + loc[1][2] + '&loc=' + loc[2][2] + '&loc=' + loc[3][2] +'&loc=' + loc[4][2] +  '&loc=' + loc[5][2]
    return mensaje
def getRuteo(loc, headers):
    """
    Ejecuta la consulta a la ruta a la API de ruteo
    """
    mensaje = prepararMensajeRuteo(loc)
    url = server + mensaje
    # Realizamos la consulta
    response = requests.request('GET', url, headers=headers, allow_redirects=False)
    return response

def destinoIsInCaba(destino, headers):
    """
    Consulta si el destino se encuentra dentro de CABA
    o si se debe calcular los costos de retorno a CABA
    """
    # url = server_datos_utiles + '?x=' + loc[5][1] + '&y=' + loc[5][0]
    mensaje = '?x=' + destino[1] + '&y=' + destino[0]
    url = server_datos_utiles + mensaje
    # Realizamos la consulta
    response = requests.request('GET', url, headers=headers, allow_redirects=False)
    
    resultado_du = response.json()

    comuna = resultado_du['comuna']
    print(comuna)

    if(resultado_du['comuna'] == ''):
        destinoInCABA = False
    else:
        destinoInCABA = True
    return destinoInCABA

def getRetornoCABA(destino, qheaders):
    """
    Consultar el punto de retorno a CABA
    mas cercano al destino
    """
    # Composición de la url
    # url_punto_retorno = server_retorno_caba + '?x=' + loc[5][1] + '&y=' + loc[5][0] + '&formato=geojson'
    url_punto_retorno = server_retorno_caba + '?x=' + destino[1] + '&y=' + destino[0] + '&formato=geojson'
    
    # Realizamos la consulta de punto de retorno a CABA
    response = requests.request('GET', url_punto_retorno, headers=qheaders, allow_redirects=False)
    return response

def getRetornoCABA_new(destino, qheaders):
    """
    Consultar el punto de retorno a CABA
    mas cercano al destino
    """
    # Composición del punto
    iDestino = {'x': destino[1], 'y': destino[0]}
    iDestino.update([('srid', 97433), ('formato', 'json')])
    print(iDestino)
    response = buscarInformacionRuteo(iDestino)
    
    return response


def buscarInformacionRuteo(request):
    try:

        callback = str(request.get('callback', ''))
        x = request.get('x', 0)
        y = request.get('y', 0)
        srid = request.get('srid', 4326)
        radio = request.get('radio', 0)
        orden = request.get('orden', 'distancia')
        limite = request.get('limite', 10)
        fullInfo = request.get('fullInfo', 'False')
        formato = request.get('formato', 'json')
        
        response = {"totalFull": 0, "instancias": [], 'total': 0}
        
        try:

            x = float(x)
            y = float(y)

            if not x != 0 or not y != 0:
                x = 0
                y = 0

        except Exception:
            x = 0
            y = 0

        try:
            srid = int(srid)

        except Exception:
            srid = 4326

        try:
            radio = float(radio)

            if radio > 0:
                if radio > 50:
                    radio = 1
            else:
                radio = 1

        except Exception:
            radio = 1

        try:
            limite = int(limite)

            if limite < 0:
                limite = 10

        except Exception:
            limite = 10
        
        punto = GEOSGeometry('SRID={2};POINT({0} {1})'.format(x, y, srid))

        if srid != settings.SRID:
            punto.transform(settings.SRID)

        objetos_ruteo = Ruteo.busquedaGeografica(x, y, srid, radio)

        obj = objetos_ruteo[0]

        latitud = obj.latitud
        longitud = obj.longitud
        

        instancia = {                
                "latitud" : latitud,
                "longitud" : longitud
        }

        response['instancias'].append(instancia)
        response['totalFull'] += 1
        response['total'] += 1

        if formato == 'geojson':

            if response['instancias']:
                res = response['instancias']
            # Implementar excepcion respuesta vacia
            else:
                res = armarEstructuraGeoLayer([], [], '', 'geojson')

            res = simplejson.dumps(res)
            #res = aplicar_callback(res, callback)
            return HttpResponse(res, mimetype="application/json")

        response_str = simplejson.dumps(response)
        #response = aplicar_callback(response, callback)
        #return HttpResponse(response, mimetype="application/json")
        return response['instancias']
    except Exception as e:
        response = simplejson.dumps({'error': e.__str__()})
        response = aplicar_callback(response, callback)
        return HttpResponse(response, mimetype="application/json")
