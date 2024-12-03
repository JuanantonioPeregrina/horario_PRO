import json
import random
import uuid
from types import SimpleNamespace  # Para crear un objeto dinámico
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login
from django.contrib import messages
from .models import HistorialProducto, Pedido, Producto, Carrito, CarritoProducto, ProductoPedido, Oferta, Categoria
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.http import JsonResponse
from django.core.mail import send_mail
from .forms import ChangeUsernameForm
from django.contrib.auth.models import AnonymousUser
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.contrib.auth.decorators import user_passes_test
from django.utils.http import urlsafe_base64_decode
from django.contrib.auth.tokens import default_token_generator
from django.urls import reverse



from .models import get_invitado_user


# Página principal
def index(request):
    return render(request, 'app/index.html')

# Vista de inicio de sesión
def inicio_sesion(request):
    # Verificar si el usuario ya está autenticado
    if request.user.is_authenticated:
        return redirect('pagina_principal')  # Redirigir directamente a la página principal si ya ha iniciado sesión

    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        # Intentar autenticar al usuario con el email y contraseña
        user = User.objects.filter(username=email).first()  # Buscar al usuario por email
        
        if user:  # Si el usuario existe
            if not user.is_active:  # Comprobar si no ha validado su cuenta
                messages.error(request, 'No has validado tu cuenta. Revisa tu correo para activarla.')
                return render(request, 'app/InicioSesion.html')
            
            # Autenticar al usuario solo si está activo
            user_authenticated = authenticate(request, username=email, password=password)
            if user_authenticated:
                login(request, user_authenticated)
                return redirect('pagina_principal')
            else:
                messages.error(request, 'Correo o contraseña incorrectos.')
        else:
            messages.error(request, 'Correo o contraseña incorrectos.')

    return render(request, 'app/InicioSesion.html')


# Página mostrada cuando el usuario ha iniciado sesión
# Página mostrada cuando el usuario ha iniciado sesión
#@login_required  # Esto asegura que solo los usuarios autenticados puedan acceder



def pagina_principal(request):
    # Mostrar solo productos activos para todos los usuarios
    productos = Producto.objects.filter(activo=True)

    # Obtener las categorías 'menu' y 'carta' primero
    categoria_menu = Categoria.objects.get(nombre='menu')
    categoria_carta = Categoria.objects.get(nombre='carta')

    # Filtrar los productos por la categoría obtenida
    categorias = {
        'menu': productos.filter(categoria=categoria_menu),
        'carta': productos.filter(categoria=categoria_carta),
    }

    # Clasificar por subcategorías dentro de 'menu' y 'carta'
    subcategorias = {
        'menu': {
            'entrantes': categorias['menu'].filter(subcategoria='entrantes'),
            'primero': categorias['menu'].filter(subcategoria='primero'),
            'segundo': categorias['menu'].filter(subcategoria='segundo'),
            'postre': categorias['menu'].filter(subcategoria='postre'),
        },
        'carta': {
            'entrantes': categorias['carta'].filter(subcategoria='entrantes'),
            'primero': categorias['carta'].filter(subcategoria='primero'),
            'segundo': categorias['carta'].filter(subcategoria='segundo'),
            'postre': categorias['carta'].filter(subcategoria='postre'),
        },
    }

    # Comprobar si el usuario es autenticado o invitado
    es_invitado = request.session.get('es_invitado', False)

    if request.user.is_authenticated:
        if request.user.is_staff:
            productos = Producto.objects.all()  # Mostrar todos los productos si es staff
        pedidos = Pedido.objects.filter(usuario=request.user)
        pedido = pedidos.last() if pedidos else None
        return render(request, 'app/PaginaPrincipal.html', {
            'productos': productos,
            'categorias': categorias,
            'subcategorias': subcategorias,
            'pedidos': pedidos,
            'pedido': pedido,
            'invitado': False,
        })

    elif es_invitado:
        invitado_id = generar_invitado_id(request)
        pedidos = Pedido.objects.filter(invitado_id=invitado_id)
        pedido = pedidos.last() if pedidos else None
        return render(request, 'app/PaginaPrincipal.html', {
            'productos': productos,
            'categorias': categorias,
            'subcategorias': subcategorias,
            'pedidos': pedidos,
            'pedido': pedido,
            'invitado': True,
            'invitado_id': invitado_id,
        })

    return redirect('inicio_sesion')



def registrarse(request):
    if request.method == 'POST':
        nombre_completo = request.POST.get('nombre_completo')
        email = request.POST.get('email')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')

        # Comprobar si las contraseñas coinciden
        if password != confirm_password:
            messages.error(request, 'Las contraseñas no coinciden.')
            return render(request, 'app/registro.html')

        # Verificar si el email ya está en uso
        if User.objects.filter(email=email).exists():
            messages.error(request, 'El correo electrónico ya está registrado.')
            return render(request, 'app/registro.html')

        # Crear el usuario inactivo
        user = User.objects.create_user(
            username=email,  # Usamos el email como username
            email=email,
            password=password
        )
        user.is_active = False  # Usuario inactivo hasta que confirme
        user.save()

        # Generar el token de activación
        token = default_token_generator.make_token(user)

        # Construir la URL de activación
        activation_link = request.build_absolute_uri(
            reverse('activar_cuenta', kwargs={'uid': user.pk, 'token': token})
        )

        # Enviar correos
        codigo_oferta = f'{user.username}_10'
        Oferta.objects.create(usuario=user, descuento=10, codigo=codigo_oferta)
        enviar_correo(
            mail=user.email,
            user=user,
            oferta=codigo_oferta,
            activation_link=activation_link
        )

        messages.success(request, 'Te hemos enviado un correo para confirmar tu cuenta.')
        return redirect('inicio_sesion')

    return render(request, 'app/registro.html')

def crear_usuario_oferta(email, password, activation_link = None):
    if User.objects.filter(username=email).exists():
        raise ValueError("El usuario ya existe")  # Evitar intentar crear un usuario duplicado
    user = User.objects.create_user(username=email, email=email, password=password)
    user.is_active = False  # El usuario estará inactivo hasta que confirme
    user.save()
    # Generar código de oferta
    codigo_oferta = f'{user.username}_10'
    Oferta.objects.create(usuario=user, descuento=10, codigo=codigo_oferta)
    enviar_correo(mail=user,user=user,oferta=codigo_oferta, activation_link=activation_link)
    

def enviar_correo(mail, user, oferta = None, activation_link = None):
    if oferta:
        send_mail(
            'Oferta de bienvenida',
            f'¡Hola {user.username}! Te hemos dado una oferta del 10%. Usa el código: {oferta}',
            'no-reply@mcnolo.com',
            [mail],
            fail_silently=False,
        )
    if activation_link:
        send_mail(
            'Activa tu cuenta',
            f'Hola {user.username}, activa tu cuenta con el siguiente enlace: {activation_link}',
            'no-reply@mcnolo.com',
            [mail],
            fail_silently=False,
        )

    send_mail(
        'Bienvenido',
        f'¡Hola {user.username}! Bienvenido a nuestra plataforma \n Muchas gracias por registrarte',
        'no-reply@mcnolo.com',
        [mail],
        fail_silently=False,
    )

def activar_cuenta(request, uid, token):
    try:
        user = User.objects.get(pk=uid)  # Usa directamente el `uid` como entero
    except User.DoesNotExist:
        user = None

    if user and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save()
        messages.success(request, 'Tu cuenta ha sido activada con éxito. Ya puedes iniciar sesión.')
        return redirect('inicio_sesion')
    else:
        messages.error(request, 'El enlace de activación es inválido o ha expirado.')
        return redirect('registrarse')

def anadir_plato(request):
    if request.method == 'POST':
        nombre_plato = request.POST.get('nombre_plato')
        descripcion = request.POST.get('descripcion')
        precio =   request.POST.get('precio')
        tiempo_preparacion = request.POST.get('tiempo_preparacion')
        #disponible = 'disponible' in request.POST
        activo = 'disponible' in request.POST
        #disponible = request.POST.get('disponible')
        imagen = request.FILES.get('imagen')

        nuevo_plato = Producto(nombre=nombre_plato, descripcion=descripcion, precio=precio, tiempo_preparacion=tiempo_preparacion, activo=activo, imagen=imagen)
        nuevo_plato.save()
        return redirect('pagina_principal')
    
def eliminar_producto(request, producto_id):
    producto = get_object_or_404(Producto, id=producto_id)
    producto.activo = False  # Marcar como inactivo en lugar de eliminar
    producto.save()
    HistorialProducto.objects.create(producto=producto, accion='eliminado')
    return redirect('pagina_principal')  # Redirige a la página principal después de eliminar

def restaurar_producto(request, producto_id):
    producto = get_object_or_404(Producto, id=producto_id)
    producto.activo = True  # Volver a activar el producto
    producto.save()
    return redirect('pagina_principal')

def cambiar_visibilidad_producto(request, producto_id):
    producto = Producto.objects.get(id=producto_id)
    producto.activo = not producto.activo  # Cambiar visibilidad
    producto.save()
    return redirect('pagina_principal')


def pedido_listo(request, pedido_id):
    pedido = get_object_or_404(Pedido, id=pedido_id)
    pedido.estado = 'listo'
    pedido.save()

    channel_layer = get_channel_layer()
    if pedido.usuario:
        group_name = f'pedido_{pedido.id}'
    else:
        invitado_id = request.session.get('invitado_id', None)
        if invitado_id:
            group_name = f'invitado_{invitado_id}'
        else:
            return JsonResponse({'error': 'Usuario no identificado'}, status=400)

    # Enviar mensaje al grupo WebSocket
    async_to_sync(channel_layer.group_send)(
        group_name,
        {
            'type': 'pedido_listo',
            'message': f'Tu pedido #{pedido.id} está listo para recoger.',
        }
    )

    return redirect('pagina_principal')



def anadir_al_carrito(request, producto_id):
    carrito = request.session.get('carrito', [])
    if producto_id not in carrito:
        carrito.append(producto_id)
    request.session['carrito'] = carrito
    messages.success(request, "Producto añadido al carrito.")
    return redirect('pagina_principal')

def agregar_al_carrito(request, producto_id):
    producto = get_object_or_404(Producto, id=producto_id)
    carrito, created = Carrito.objects.get_or_create(usuario=request.user)
    carrito_producto, created = CarritoProducto.objects.get_or_create(carrito=carrito, producto=producto)
    carrito_producto.cantidad += 1
    carrito_producto.save()
    carrito.calcular_total()
    return JsonResponse({'status': 'success', 'total': carrito.total})

import uuid
@csrf_exempt
def finalizar_compra(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        cart = data.get('cart', [])
        total = data.get('total', 0)
        nota_especial = data.get('nota_especial', '')

        if not cart:
            return JsonResponse({'error': 'El carrito está vacío.'}, status=400)

        # Determinar el usuario o el invitado
        if request.user.is_authenticated:
            user = request.user  # Usuario autenticado
            invitado_id = None  # No aplica para usuarios autenticados
        else:
            # Generar un `invitado_id` único si no existe
            #if 'invitado_id' not in request.session:
                #request.session['invitado_id'] = str(uuid.uuid4())
            #invitado_id = request.session['invitado_id']
            invitado_id = request.session['invitado_id']
            #user = get_invitado_user()  # Usuario genérico "invitado_default"
            user = None
        # Crear el pedido
        pedido = Pedido.objects.create(
            usuario=user,  # Usuario autenticado o "invitado_default"
            invitado_id=invitado_id,  # Solo se asigna para invitados
            total=total,
            nota_especial=nota_especial,
        )
        
        print(f"Pedido creado: {pedido}, invitado_id={pedido.invitado_id}")
        # Guardar productos del pedido
        for item in cart:
            producto = Producto.objects.get(nombre=item['name'])
            ProductoPedido.objects.create(pedido=pedido, producto=producto, cantidad=1)

        # Crear sesión de pago en Stripe
        try:
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[
                    {
                        'price_data': {
                            'currency': 'eur',
                            'product_data': {'name': item['name']},
                            'unit_amount': int(float(item['price']) * 100),
                        },
                        'quantity': 1,  # Asume que siempre es 1 por simplicidad
                    }
                    for item in cart
                ],
                mode='payment',
                success_url=f'http://127.0.0.1:8000/success/?pedido_id={pedido.id}',
                cancel_url='http://127.0.0.1:8000/cancel/',
            )

            # Vincular el WebSocket para el pedido
            channel_layer = get_channel_layer()
            if invitado_id:  # Si es un invitado
                group_name = f'invitado_{invitado_id}'
            else:  # Si es un usuario autenticado
                group_name = f'pedido_{pedido.id}'

            # Enviar notificación al grupo WebSocket (solo si se genera el pedido correctamente)
            async_to_sync(channel_layer.group_add)(
                group_name,
                {
                    'type': 'pedido_creado',
                    'message': f'Tu pedido #{pedido.id} se está procesando.',
                }
            )

            return JsonResponse({'url': session.url})  # Devuelve la URL de Stripe
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'error': 'Método no permitido.'}, status=405)

def generar_invitado_id(request):
    if 'invitado_id' not in request.session:
        request.session['invitado_id'] = str(uuid.uuid4())
        request.session['es_invitado'] = True  # Marcamos al usuario como invitado
    print("Generado invitado_id:", request.session['invitado_id'])  # Confirmar ID generado
    return request.session['invitado_id']



def obtener_estado_pedido(request, pedido_id):
    pedido = Pedido.objects.get(id=pedido_id, usuario=request.user)  # Asegúrate de que el pedido pertenece al usuario autenticado
    return JsonResponse({'estado': pedido.get_estado_display()})  # Devuelve el estado legible del pedido

def obtener_pedido(request, pedido_id):
    try:
        pedido = Pedido.objects.get(id=pedido_id, usuario=request.user)
        productos_pedido = ProductoPedido.objects.filter(pedido=pedido)

        productos = [
            {
                'nombre': producto_pedido.producto.nombre,
                'precio': producto_pedido.producto.precio,
                'cantidad': producto_pedido.cantidad
            }
            for producto_pedido in productos_pedido
        ]

        return JsonResponse({
            'productos': productos,
            'total': pedido.total
        })
    
    except Pedido.DoesNotExist:
        return JsonResponse({'error': 'Pedido no encontrado.'}, status=404)
    
def comprobar_oferta(request):
    data = json.loads(request.body)
    codigo = data.get('codigo')  # Obtener el código enviado desde el formulario
    # Buscar la oferta en la base de datos
    oferta = Oferta.objects.filter(codigo=codigo).first()

    if oferta:
        # Si se encuentra una oferta válida, calcular el descuento
        oferta_aplicable = 1 - (oferta.descuento / 100)
        return JsonResponse({'oferta_aplicable': oferta_aplicable})
    else:
        # Si el código de la oferta no es válido
        return JsonResponse({'error': 'Código de oferta no válido'}, status=400)

@login_required   
def change_username(request):
    if request.method == 'POST':
        new_username = request.POST.get('username')
        if new_username:
            request.user.username = new_username
            request.user.save()
            messages.success(request, 'Nombre de usuario cambiado con éxito')
            return redirect('pagina_principal')  # Redirigir después de cambiar
        else:
            messages.error(request, 'Por favor, introduce un nombre de usuario válido')
    return render(request, 'app/change_username.html', {'user': request.user})

@login_required
def change_image(request):
    if request.method == 'POST':
        profile = request.user.profile  
        image = request.FILES.get('image')
        if image:
            profile.foto = image  # 'foto' es el campo de imagen en el modelo Profile
            profile.save()
            messages.success(request, 'Imagen de perfil actualizada con éxito')
            return redirect('pagina_principal')
        else:
            messages.error(request, 'Por favor, selecciona una imagen válida')
    return render(request, 'app/change_image.html')


from django.contrib.auth.models import AnonymousUser


def invitado(request):
    request.session['es_invitado'] = True
    if 'invitado_id' not in request.session:
        request.session['invitado_id'] = str(uuid.uuid4())
    return redirect('pagina_principal')

import stripe
from django.conf import settings
from django.shortcuts import render, redirect
from django.http import JsonResponse

# Configura tu clave secreta de Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY


def procesar_pago(request):
    if request.method == "POST":
        # Obtener detalles del pedido
        total = request.POST.get("total")
        try:
            # Crear el Intento de Pago (PaymentIntent)
            intent = stripe.PaymentIntent.create(
                amount=int(float(total) * 100),  # El total en centavos
                currency="eur",  # Moneda
                payment_method_types=["card"],  # Métodos de pago disponibles
            )
            # Retornar el ID del Intento de Pago a la plantilla
            return JsonResponse({"clientSecret": intent["client_secret"]})
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)
    return render(request, "app/procesar_pago.html")

from django.http import JsonResponse
import stripe


stripe.api_key = settings.STRIPE_SECRET_KEY  # Usar la clave secreta


@csrf_exempt
def crear_sesion_pago(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        cart = data.get('cart', [])
        total = data.get('total', 0)
        nota_especial = data.get('nota_especial', '')

        if not cart:
            return JsonResponse({'error': 'El carrito está vacío.'}, status=400)

        # Asigna el usuario o el usuario genérico para invitados
        user = request.user if request.user.is_authenticated else get_invitado_user()

        # Crear el pedido
        pedido = Pedido.objects.create(
            usuario=user,
            total=total,
            nota_especial=nota_especial,
        )

        # Guardar los productos del pedido y construir la factura
        factura_string = f"Factura para el pedido #{pedido.id}:\n\n"
        for item in cart:
            producto = Producto.objects.get(nombre=item['name'])
            cantidad = item.get('cantidad', 1)
            ProductoPedido.objects.create(
                pedido=pedido,
                producto=producto,
                cantidad=cantidad,
            )
            factura_string += f"- {producto.nombre}: {producto.precio}€ x {cantidad} unidades\n"

        # Agregar total y nota especial a la factura
        factura_string += f"\nTotal: {total}€\n"
        if nota_especial:
            factura_string += f"\nNota Especial: {nota_especial}\n"
        factura_string += "\nGracias por su compra!"

        try:
            # Crear sesión de pago en Stripe
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[
                    {
                        'price_data': {
                            'currency': 'eur',
                            'product_data': {'name': item['name']},
                            'unit_amount': int(float(item['price']) * 100),
                        },
                        'quantity': item.get('cantidad', 1),
                    }
                    for item in cart
                ],
                mode='payment',
                success_url=f'http://127.0.0.1:8000/success/?pedido_id={pedido.id}',
                cancel_url='http://127.0.0.1:8000/cancel/',
            )

            # Enviar email con la factura
            if user.email:  # Asegurarse de que el usuario tenga un correo
                send_mail(
                    subject=f'Confirmación de tu pedido #{pedido.id}',
                    message=factura_string,
                    from_email='no-reply@mcnolo.com',
                    recipient_list=[user.email],
                    fail_silently=False,
                )

            return JsonResponse({'url': session.url})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'error': 'Método no permitido.'}, status=405)




from django.template.loader import render_to_string

def payment_success(request):
    # Obtener el pedido utilizando el parámetro `pedido_id`
    pedido_id = request.GET.get('pedido_id')
    if not pedido_id:
        messages.error(request, 'No se proporcionó un pedido válido.')
        return redirect('pagina_principal')

    try:
        pedido = Pedido.objects.get(id=pedido_id)
    except Pedido.DoesNotExist:
        messages.error(request, 'El pedido no existe.')
        return redirect('pagina_principal')

    # Obtener los productos del pedido
    productos = ProductoPedido.objects.filter(pedido=pedido)

    # Renderizar la factura como HTML
    factura_html = render_to_string('app/factura.html', {
        'pedido': pedido,
        'productos': productos,
    })

    # Redirigir a la página de éxito con la factura
    return render(request, 'app/success.html', {
        'pedido': pedido,
        'productos': productos,
        'factura_html': factura_html,
    })


def payment_cancel(request):
    return render(request, 'app/cancel.html')


temporary_data = {}

def forgot_password(request):
    if request.method == 'POST':
        email = request.POST.get('email')  # Obtiene el correo del formulario
        if email:
            # Generar un código numérico aleatorio
            code = random.randint(100000, 999999)

            # Guardar temporalmente el correo y código (para pruebas, sin BBDD)
            temporary_data['email'] = email
            temporary_data['code'] = str(code)

            # Simular el envío de correo
            user = SimpleNamespace(username=email.split('@')[0])
            try:
                enviar_correoVerificacion(email, user, code)
                return redirect('cambio_password')  # Redirigir a la nueva página
            except Exception as e:
                return JsonResponse({'success': False, 'message': str(e)})

    return render(request, 'app/forgot_password.html')

from django.contrib.auth.hashers import make_password
def cambio_password(request):
    email = temporary_data.get('email')  # Recupera el correo guardado temporalmente

    if not email:  # Si no hay correo temporal, redirigir al inicio
        return redirect('forgot_password')

    if request.method == 'POST':
        entered_code = request.POST.get('code')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')

        # Verificar que el código ingresado sea correcto
        if entered_code != temporary_data.get('code'):
            messages.error(request, 'Código incorrecto')
            return render(request, 'app/cambio_password.html', {'email': email})

        # Verificar que las contraseñas coincidan
        if new_password != confirm_password:
            messages.error(request, 'Las contraseñas no coinciden')
            return render(request, 'app/cambio_password.html', {'email': email})

        # Verificar si el username (que en este caso es el email) pertenece a un usuario existente
        try:
            user = User.objects.get(username=email)  # Busca al usuario por el campo `username`
        except User.DoesNotExist:
            messages.error(request, 'No se encontró un usuario con ese correo electrónico')
            return render(request, 'app/cambio_password.html', {'email': email})

        # Cambiar la contraseña del usuario
        user.password = make_password(new_password)  # Usar `make_password` para encriptar la contraseña
        user.save()  # Guardar los cambios en la base de datos

        # Éxito: Mostrar mensaje y redirigir
        messages.success(request, 'Contraseña cambiada exitosamente. Ahora puedes iniciar sesión.')
        return redirect('inicio_sesion')

    return render(request, 'app/cambio_password.html', {'email': email})

def enviar_correoVerificacion(mail, user, oferta):
    send_mail(
        'Código de Verificacion',
        f'¡Hola! Tu código de confirmación es:{oferta}',
        'no-reply@tuapp.com',
        [mail],
        fail_silently=False,
    )
@user_passes_test(lambda u: u.is_superuser)
def gestionar_pedidos(request):
    if request.method == 'POST':
        accion = request.POST.get('accion')
        pedido_id = request.POST.get('pedido_id')

        pedido = get_object_or_404(Pedido, id=pedido_id)

        try:
            # Lógica para ejecutar las acciones
            if accion == 'aceptar':
                pedido.estado = 'aceptado'
            elif accion == 'rechazar':
                pedido.estado = 'rechazado'
            elif accion == 'poner_en_proceso':
                pedido.estado = 'en_proceso'
            elif accion == 'finalizar':
                pedido.estado = 'finalizado'
            elif accion == 'enviado':
                pedido.estado = 'enviado'
            elif accion == 'preparar_recogida':
                pedido.estado = 'recoger'
            else:
                return JsonResponse({'error': 'Acción no válida'}, status=400)

            pedido.save()
            return JsonResponse({'mensaje': f'Pedido {pedido_id} actualizado a {pedido.estado}.'})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    # Si es GET, renderiza una plantilla para listar pedidos
    pedidos = Pedido.objects.all()
    return render(request, 'app/gestionar_pedidos.html', {'pedidos': pedidos})
