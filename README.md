# Cartero

App de escritorio para Mac y Windows que manda a cada cliente **su** factura en
PDF por email. Sirve para cualquier empresa y cualquier programa de facturación.
Los clientes sin email se apuntan para avisarlos por teléfono, y nada se envía
dos veces. Es gratis de usar, y las facturas no salen del ordenador salvo en el
propio correo.

El nombre se cambia en una sola línea: `NOMBRE_APP` en `nucleo/config.py`.

## Cómo sabe de quién es cada PDF

En `nucleo/emparejar.py` busca en el texto del PDF, de más seguro a menos:

1. El **NIF** de un cliente. El de tu empresa no cuenta, y si no lo has escrito
   se detecta solo porque sale en más de la mitad de las facturas.
2. El **email** de un cliente.
3. Un **texto ancla** opcional, si tu programa pone siempre el cliente debajo de
   una línea fija (en EjidoSoft, `E-MAIL:`).
4. El **nombre** del cliente o un **alias aprendido**, esté donde esté. Admite
   formas jurídicas distintas (S.L., S.A.T.…) y una errata.

Si dos clientes encajan casi igual, la factura queda **Dudosa** y no se envía
hasta que alguien elija. Cuando asignas una a mano, la app aprende el NIF o el
nombre para la próxima vez.

## Cada mes

**Mes pasado** (o **Este mes**) → **Buscar facturas** → revisar colores →
**Enviar todas las listas** → llamar a los de la pestaña **Por teléfono**.

## Datos

Todo va en un SQLite en `~/Library/Application Support/Cartero` (Mac) o
`%APPDATA%\Cartero` (Windows). Con la variable de entorno `CARTERO_DATOS` se
puede usar otra carpeta, por ejemplo una de red, para que varios ordenadores
compartan el historial. La contraseña del correo va al llavero del sistema.

## Desarrollo

```bash
python3 -m venv venv
venv/bin/pip install -r requirements-dev.txt
venv/bin/python main.py                                         # abrir la app
QT_QPA_PLATFORM=offscreen venv/bin/python -m pytest pruebas -q  # pruebas
```

`pruebas/reales/` guarda datos reales de clientes para probar y **no** se sube
a GitHub.

## Compilar

- **Mac** (en un Mac): `bash empaquetado/compilar_mac.sh` → `dist/Cartero-<versión>.dmg`
- **Windows**: lo compila GitHub Actions (`.github/workflows/compilar.yml`) en
  cada `git push`, y el instalador queda en *Actions* → *Artifacts*. Con una
  etiqueta (`git tag v0.1.0 && git push --tags`) se publica además una
  *Release* con el .dmg y el .exe.
- `Cartero --autoprueba factura.pdf` comprueba, sin abrir ventanas, que la app
  empaquetada lee PDF y monta y envía correos (a un servidor falso local).

Las apps van sin firmar:

- **Mac:** la primera vez, clic derecho en la app → Abrir.
- **Windows:** SmartScreen → «Más información» → «Ejecutar de todas formas».

## Estructura

```
main.py           entrada (asistente la primera vez, luego la ventana)
nucleo/           datos, emparejar, analisis, correo, envio, importar, autoprueba
interfaz/         asistente, páginas de ajustes, ventana, diálogos, estilo
pruebas/          pytest: núcleo e interfaz, con PDF de prueba y servidor SMTP falso
empaquetado/      PyInstaller, .dmg, instalador Windows (Inno Setup), icono
```
