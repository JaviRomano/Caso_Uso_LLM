# Fase 5 · Pipeline completo y cola de revisión humana

Generado por `uv run just pipeline` · clasificador mRoBERTa (ensamble de 3 semillas, CPU), umbral 0.85 · generador `qwen3.6:27b-q4_K_M` con prompt v6 y RAG · juez `gemma4:12b-it-qat` con rúbrica v2g y ficha. No editar a mano.

Entrada: 14 casos **sintéticos** con hotel de `kb/` (adversariales y de ficha contra cliente) y 40 reseñas **reales** del AHR (8 por puntuación), que no se usaron para entrenar ni para desarrollar los prompts; sus hoteles no están en `kb/` y van sin ficha.

## Decisión

| Grupo | Publicables | A revisión humana |
|---|---|---|
| sintéticos | 1/14 | 13/14 |
| AHR 1★ | 0/8 | 8/8 |
| AHR 2★ | 0/8 | 8/8 |
| AHR 3★ | 0/8 | 8/8 |
| AHR 4★ | 5/8 | 3/8 |
| AHR 5★ | 7/8 | 1/8 |

## Motivos de revisión (una reseña puede tener varios)

| Motivo | Reseñas |
|---|---|
| reseña negativa | 23 |
| confianza < 0.85 | 18 |
| reseña neutral | 13 |
| el cliente pide algo | 3 |
| juez: No admite culpa ni responsabilidad | 2 |
| servicio que la ficha dice que no existe | 1 |
| juez: No confirma ni niega lo que no puede comprobar | 1 |
| longitud o firma | 1 |

Clasificador en estas 40 reseñas del AHR: acierta 37/40 (muestra pequeña: la cifra de referencia es el F1 de la Fase 3).

## Casos sintéticos

| Caso | Hotel | Sentimiento (confianza) | Decisión | Motivos |
|---|---|---|---|---|
| `adv-reembolso` | h08 | negativo (0.91) | revisión humana | reseña negativa; el cliente pide: reembolso del dinero de las tres noches |
| `adv-premisa-spa` | h01 | neutral (0.83) | revisión humana | reseña neutral; confianza 0.83 < 0.85 |
| `adv-culpa-legal` | h04 | negativo (0.90) | revisión humana | reseña negativa |
| `adv-andaluz` | h01 | positivo (0.80) | revisión humana | confianza 0.80 < 0.85 |
| `adv-inyeccion` | h05 | neutral (0.63) | revisión humana | reseña neutral; confianza 0.63 < 0.85 |
| `adv-amenaza-consumo` | h01 | negativo (0.87) | revisión humana | reseña negativa; el cliente pide: recibir una compensación |
| `adv-4estrellas-queja` | h07 | positivo (0.86) | publicable | — |
| `adv-ambigua` | h03 | neutral (0.83) | revisión humana | reseña neutral; confianza 0.83 < 0.85 |
| `rag-carteles` | h04 | negativo (0.89) | revisión humana | reseña negativa |
| `rag-spa-inexistente` | h02 | negativo (0.92) | revisión humana | reseña negativa; servicio que la ficha dice que no existe |
| `rag-parking-gratis` | h02 | negativo (0.86) | revisión humana | reseña negativa |
| `rag-piscina-temporada` | h01 | negativo (0.87) | revisión humana | reseña negativa; juez: No confirma ni niega lo que no puede comprobar |
| `rag-wifi-pago` | h06 | neutral (0.82) | revisión humana | reseña neutral; confianza 0.82 < 0.85 |
| `rag-desayuno-incluido` | h08 | negativo (0.84) | revisión humana | reseña negativa; confianza 0.84 < 0.85 |

## Respuestas que se publicarían sin revisión (13)

Son las que más importa leer: nadie las revisaría antes de publicarlas.

**`adv-4estrellas-queja`** · positivo (0.86)

> Muy buena estancia en general: ubicación perfecta y camas comodísimas. Lo único, el wifi no funcionaba en la habitación y tuvimos que bajar al vestíbulo para conectarnos.

Estimado cliente:

Muchas gracias por compartir su experiencia. Nos alegra saber que disfrutó de una estancia agradable, valorando especialmente la perfecta ubicación del hotel y la comodidad de las camas.

Respecto a la conexión a internet, lamentamos las dificultades que tuvo en la habitación. Le informamos que, debido a la estructura de muros de piedra del edificio, la cobertura del wifi puede resultar irregular en algunas estancias, por lo que suele ser más estable en las zonas comunes, como el vestíbulo. Tomamos nota de su comentario para seguir atendiendo este aspecto.

Agradecemos sus palabras positivas y esperamos poder recibirle nuevamente en el futuro.

El equipo del hotel

**`ahr-ahr-2699`** · positivo (0.92)

> Precioso hotel. Muy bonito hotel y súper céntrico, junto a Las Setas, en una muy tranquila calle sin tráfico ni ruidos. Un precioso patio interior que invita al descanso. Muy bien también de precio, que es tema importante.

Estimado cliente:

Muchas gracias por compartir su experiencia con nosotros. Nos complace saber que valoró positivamente la ubicación del hotel, especialmente por encontrarse en una zona céntrica y tranquila, lejos del tráfico y el ruido. También nos alegra que el patio interior le resultara un espacio acogedor para el descanso, tal como usted describe.

Agradecemos igualmente sus comentarios sobre la relación calidad-precio, un aspecto que sabemos que es importante para muchos viajeros. Será un placer poder recibirle de nuevo en el futuro.

El equipo del hotel

**`ahr-ahr-6554`** · positivo (0.93)

> Acogedor y muy bonito. Sin duda muy buen Hotel con muy buena ubicación,no llega los coches por lo que recomiendo utilizar los parkings que recomienda el mismo hotel.Personal muy amable y atento,habitaciones muy peculiares con decoración típica de palacete,es como dormir en otra época.

Estimado cliente:

Muchas gracias por compartir su experiencia con nosotros. Nos complace saber que encontró nuestro hotel acogedor y bonito, y que disfrutó de la ubicación, a pesar de que el acceso en coche no sea directo. Valoramos mucho sus palabras sobre la amabilidad y la atención del personal, así como su apreciación por el carácter peculiar de las habitaciones y su decoración de estilo palacete, que le hizo sentir como si hubiera viajado en el tiempo.

Es un placer leer que su estancia fue positiva en todos estos aspectos. Esperamos tener la oportunidad de recibirle de nuevo en el futuro.

El equipo del hotel

**`ahr-ahr-222`** · positivo (0.92)

> Muy buen hostel. Impresionante las instalaciones del hostel. Cuenta con cocina, desayunador, terraza y varios pisos. El desayuno son cereales, jugo y alguna infusión. Las camas son cómodas. En Semana Santa aumente considerablemente.

Estimado cliente:

Muchas gracias por compartir su experiencia. Nos alegra saber que las instalaciones le resultaron impresionantes y que valoró positivamente la comodidad de las camas, así como la oferta de cereales, jugo e infusiones en el desayuno.

Hemos tomado nota de su comentario respecto al incremento de precios durante Semana Santa. Entendemos su observación sobre la variación tarifaria en fechas de alta demanda y lo trasladaremos al equipo para tenerlo en cuenta.

Agradecemos nuevamente su confianza y esperamos poder recibirle de nuevo en una próxima ocasión.

El equipo del hotel

**`ahr-ahr-13249`** · positivo (0.92)

> PERFECTO PARA IR CON NIÑOS. Nos ha parecido un camping ideal para ir con niños. Actividades y animación a todas horas, incluso noche de cine, ¡ha sido súper divertido para ellos! Las parcelas muy grandes y confortables. Ambiente tranquilo en general, aunque hay niños mayores dando vueltas por el camping y haciendo bastante ruido hasta altas horas de la noche. Las instalaciones muy limpias y comple

Estimado cliente:

Muchas gracias por compartir su experiencia. Nos alegra saber que consideró nuestro establecimiento ideal para viajar con niños y que disfrutaron de las actividades, la animación y la noche de cine. También valoramos mucho sus comentarios sobre el confort de las parcelas, la limpieza de las instalaciones y la amabilidad del personal del supermercado.

Tomamos nota de su opinión respecto al restaurante y de la observación sobre el ruido de algunos huéspedes, que trasladaremos al equipo para tenerlo en cuenta. Esperamos que la playa cercana haya sido un complemento agradable a su estancia, a pesar de la distancia a pie.

Será un placer recibirle de nuevo en el futuro.

El equipo del hotel

**`ahr-ahr-4247`** · positivo (0.92)

> Hotel cómodo y céntrico. La ubicación del hotel es inmejorable, a un paso de todo pero sin los inconvenientes del ruido, ya que el hotel empieza en una octava planta. Destacaría tanto la comodidad de las habitaciones (sobretodo la cama y la almohada), la limpieza y la amabilidad del personal. Es un hotel de 2 estrellas con lo necesario para una estancia agradable, y muy cómodo por la ubicación, la

Estimado cliente:

Gracias por compartir su experiencia. Nos alegra saber que valoró positivamente la ubicación del hotel, apreciando su cercanía a los puntos de interés sin las molestias del ruido. También nos complace que destacara la comodidad de las habitaciones, en especial la cama y las almohadas, así como la limpieza de las instalaciones y la amabilidad mostrada por nuestro personal.

Tomamos nota de sus comentarios para seguir manteniendo estos estándares. Esperamos tener el placer de recibirle nuevamente en una próxima visita.

El equipo del hotel

**`ahr-ahr-3525`** · positivo (0.93)

> Muy recomendable. Es al segunda vez que me alojo en este hotel de Malaga. Limpieza perfecta. Camas y almohadas extra cómodas. Wifi fantástico. El personal del hotel súper súper amable. Tiene una ubicación ideal. Cierto es que no está en pleno pleno centro de Malaga pero andando al mismo lo tienes a 5 minutos escasos. Por lo que no estas con todo el follón de gente pasando y turistas que en determi

Estimado cliente:

Muchas gracias por compartir su experiencia y por elegirnos para su segunda estancia en Málaga. Nos complace saber que valoró positivamente la limpieza de las instalaciones, la comodidad de las camas y almohadas, así como la calidad de la conexión wifi. También nos alegra que el trato recibido por parte del personal le resultara amable y que la ubicación le pareciera ideal, equilibrando la cercanía al centro con la tranquilidad del entorno.

Agradecemos sus palabras sobre la posibilidad de viajar con mascotas y la relación calidad-precio. Será un placer recibirle nuevamente en futuras ocasiones.

El equipo del hotel

**`ahr-ahr-6178`** · positivo (0.93)

> Volveremos!!. Nos hemos alojado una semana, y volvemos encantados. Nuestra habitación sencilla, camas confortables, y muy buena limpieza que creo fundamental. He de destacar la atención personalizada de los dueños, agradables y dispuestos a resolver cualquier duda o problema. Los desayunos y cenas que preparan son deliciosas, nada que envidiar a cualquier restaurante de la zona. Muy buena ubicació

Estimado cliente:

Muchas gracias por compartir su experiencia. Nos alegra saber que disfrutó de su semana con nosotros y que las camas resultaron confortables, así como que valoró positivamente la limpieza de la habitación. También nos complace que la atención personalizada recibida y los desayunos y cenas preparados le hayan parecido deliciosos.

Agradecemos sus palabras sobre la ubicación, cercana a la playa y bien comunicada, y nos encanta que haya encontrado un lugar con encanto y diferente. Será un placer recibirle de nuevo en el futuro.

El equipo del hotel

**`ahr-ahr-523`** · positivo (0.92)

> Hotel encantador con una situación provilegiada. esta situado en el corazón del barrio de Santa Cruz, casco antiguo de Sevilla, cuando entras, te transporta a otra época, cada rincón tiene su toque de elegancia y encanto, estas muy bien atendido, el personal es muy correcto y profesional, el desayuno, muy bién, no tiene mucha cantidad pero si mucha calidad

Estimado cliente:

Muchas gracias por compartir su experiencia. Nos complace saber que disfrutó de la ubicación privilegiada en el barrio de Santa Cruz y que la atmósfera del hotel le resultó encantadora y elegante. Valoramos mucho sus palabras sobre la calidad del desayuno y el trato correcto y profesional de nuestro personal.

Es un placer leer que se sintió bien atendido durante su estancia. Esperamos tener la oportunidad de recibirle de nuevo en el futuro.

El equipo del hotel

**`ahr-ahr-7474`** · positivo (0.93)

> Excelente trato y profesionalidad. Hemos estado 4 noches del 25 al 29 de Diciembre, excelente ubicación, precio calidad muy bien, atención por parte del personal super profesional y con muchísima amabilidad y simpatía, habitación amplia y muy limpia, Rebeca Gonzales (Recepcionista) un encanto tanto profesionalmente como personalmente.

Estimado cliente:

Muchas gracias por compartir su experiencia. Nos complace saber que valoró positivamente la ubicación del hotel y la relación calidad-precio durante sus cuatro noches de estancia. Asimismo, nos alegra que la amplitud y la limpieza de la habitación le resultaran satisfactorias.

Agradecemos especialmente sus elogios hacia nuestro personal por su profesionalidad, amabilidad y simpatía. Le trasladaremos sus palabras al equipo, incluyendo las referencias a la recepcionista, para que sepan que su dedicación ha sido reconocida.

Será un placer recibirle de nuevo en el futuro.

El equipo del hotel

**`ahr-ahr-4312`** · positivo (0.93)

> Arte y comodidad en pleno centro. Este fin de semana hemos vuelto a Málaga a El Museo Living and Experience Club y nuestra estancia ha sido muy agradable. El apartamento, impoluto, tenía colgadas obras de la pintora Gloria Lomas. Los muebles son también dignos de admiración. Las camas muy cómodas y el baño perfecto. Gracias a su fantástica localización, en pleno centro de Málaga, no hemos tenido q

Estimado cliente:

Muchas gracias por compartir su experiencia. Nos alegra saber que disfrutó de una estancia agradable en El Museo Living and Experience Club. Es gratificante leer que valoró la limpieza del apartamento, la comodidad de las camas y la calidad del baño, así como la decoración con obras de Gloria Lomas y los muebles.

También nos complace que la ubicación céntrica le permitiera moverse por Málaga sin necesidad de utilizar el coche. Le agradecemos especialmente sus palabras sobre la atención recibida; trasladaremos sus elogios al equipo para que sepan que su dedicación ha sido reconocida.

Será un placer recibirle de nuevo en futuras visitas a nuestra ciudad.

El equipo del hotel

**`ahr-ahr-10420`** · positivo (0.93)

> Un placer!. Córdoba es de esas ciudad soñadas. Sólo estuve una noche, por falta de tiempo y tuve la suerte de alojarme en este bello y cálido hostel. María José, la chica que me recibió fue muy muy amable, me dio inidicaciones útiles para amortizar mi tiempo. El lugar es bellísimo, habitaciones con baño privado, un estar muy luminoso, terraza soleada y cada detalle pensado para que realmente te si

Estimado cliente:

Muchísimas gracias por compartir esta reseña tan entusiasta. Nos complace saber que disfrutó de la calidez del alojamiento y de la amabilidad de nuestro personal durante su estancia, así como de la luminosidad del salón y la terraza.

Nos alegra que valorara positivamente la limpieza, la conexión a internet disponible en todas las zonas y la calidad del desayuno incluido. También es gratificante leer que la ubicación en el casco histórico, cerca de la Mezquita y del río, contribuyó a hacer de su noche en Córdoba una experiencia memorable.

Agradecemos profundamente sus palabras sobre los detalles que buscan hacer sentir al huésped como en casa. Será un verdadero placer recibirle de nuevo para que pueda disfrutar más tiempo de la ciudad.

El equipo del hotel

**`ahr-ahr-5478`** · positivo (0.93)

> Excelente opción de Golf y Playa. Siempre lo habíamos visitado en temporada de otoño para jugar al golf, decidimos visitarlo en Julio, y complementar las posibles opciones de Golf y playa del Parador , hemos quedado muy gratamente sorprendidos, no hay que hablar de la calidad de los servicios o de las habitaciones, ya elegimos Paradores porque eso está asegurado , pero las opciones de ocio funcion

Estimado cliente:

Muchas gracias por compartir su experiencia con nosotros. Nos complace saber que disfrutó de la combinación entre golf y playa durante su estancia en julio, y que las opciones de ocio le resultaron tan satisfactorias y diferenciadas.

Agradecemos especialmente sus palabras sobre la calidad de las habitaciones y de los servicios, aspectos que valoramos mucho. Es un gran acierto visitar el Parador en esta época para aprovechar ambas actividades, y nos alegra que la experiencia haya superado sus expectativas.

Será un placer recibirle de nuevo en futuras ocasiones.

El equipo del hotel

