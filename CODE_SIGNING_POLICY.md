# Política de firma de código

Free code signing provided by [SignPath.io](https://about.signpath.io/),
certificate by [SignPath Foundation](https://signpath.org/).

Los ejecutables de Windows de Cartero Facturas (`Cartero Facturas.exe` y el
instalador) se compilan en GitHub Actions a partir de este repositorio y se
firman con el certificado de SignPath Foundation. Solo se firman las versiones
publicadas con una etiqueta `vX.Y.Z`.

## Equipo

- Autor, revisor y aprobador de las firmas: Juan González Haro
  ([@ualjgh120](https://github.com/ualjgh120)).

Todas las cuentas del equipo usan verificación en dos pasos en GitHub y en
SignPath.

## Privacidad

Este programa no transfiere información a ningún sistema en red salvo que lo
pida expresamente el usuario o la persona que lo instala y lo maneja. En
concreto, solo se conecta al servidor de correo (SMTP) que el usuario
configura, para enviar las facturas que él mismo decide enviar. No hay
telemetría, analítica ni comprobación de actualizaciones. Los datos se guardan
en el propio ordenador (o en la carpeta que indique `CARTERO_DATOS`) y la
contraseña del correo va al llavero del sistema.
