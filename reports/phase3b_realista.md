# Fase 3b · Evaluación realista del clasificador

Generado por `uv run just realista` · opción A, ensamble de semillas [42, 43, 44] (config `bc2b14b1`). No editar a mano.

## 1. Robustez: variantes de `coah_test` (n=269)

Las variantes son sintéticas y no deberían cambiar la etiqueta (salvo `solo_titulo`, que quita información). *Cambia* = % de reseñas cuya predicción difiere de la del texto original.

| Variante | F1 macro | IC 95 % | Cambia | F1 neutral |
|---|---|---|---|---|
| original | 0.797 | 0.732–0.853 | 0.0% | 0.535 |
| sin_titulo | 0.781 | 0.718–0.838 | 4.5% | 0.519 |
| solo_titulo | 0.730 | 0.669–0.791 | 17.1% | 0.486 |
| informal | 0.810 | 0.746–0.863 | 1.5% | 0.563 |
| erratas | 0.791 | 0.730–0.848 | 3.7% | 0.522 |
| andaluz | 0.783 | 0.722–0.841 | 4.5% | 0.513 |

## 2. Reseñas reales de otra web: SFU hoteles (ciao.es, n=50)

Solo hay 1–2★ y 4–5★. Acierto: **78.0%**; 8 reseñas predichas como neutral (cuentan como error).

| real \ pred | negativo | neutral | positivo |
|---|---|---|---|
| negativo | 21 | 4 | 0 |
| neutral | 0 | 0 | 0 |
| positivo | 3 | 4 | 18 |

Errores:

- `hoteles_yes_5_25` real positivo → negativo: «Soy cliente de este hostal desde hace mucho tiempo y me da pena ver opiniones de gente que ni_tan_siquiera han pasado unan noche estado: es totalmente injusto. La localizacion es inmejorable, justo de…»
- `hoteles_yes_4_9` real positivo → neutral: «Bueno, mi opinión sólo es referente a la terraza de este hotel, donde puedes tomar unas copas en un ambiente veraniego bajo el cielo de Madrid. Viendo el edificio de Telefónica, y ese caballo que apar…»
- `hoteles_no_2_19` real negativo → neutral: «He estado hospedado en este establecimiento y como mayor ventaja tiene su precio asequible y su localización en el centro de Madrid, situado en_la_zona_de el barrio de Salamanca estos apartamentos est…»
- `hoteles_yes_4_6` real positivo → neutral: «Para ser franca este hotel no es nada del_otro_mundo, la entrada es un tanto cutre y vieja, pero el resto de el hotel mas o menos esta bien, el personal tampoco es que este muy atento, si vas a recepc…»
- `hoteles_yes_4_10` real positivo → negativo: «La semana pasada, por trabajo tuve que estar tres días en Madrid, y nos alojaron en este hotel, ya_que era el más cercano a las oficinas de la empresa. Una vez pagado el taxi desde el aeropuerto hasta…»
- `hoteles_yes_5_2` real positivo → negativo: «Debido_a mis asiduos viajes a mi tierra y a que Vueling sólo tiene un vuelo de regreso a Madrid a las 12_de_la_noche, y como siempre llega tarde, tenemos que ver nos obligados a dormir en Madrid. Somo…»
- `hoteles_yes_4_11` real positivo → neutral: «La semana santa la decidimos pasar en la capital ya_que ya teniamos ganas de conocer esta bella ciudad. Donde nos alojamos? unos amigos nuestros que estuvieron en Madrid nos aconsejaron este hotel, el…»
- `hoteles_no_1_5` real negativo → neutral: «Reservé una habitación doble con desayuno para que negar lo atraído por el precio, 155 € por 3 noches en un cuatro estrellas a muy pocos metros de Plaza_España. Se trata de una edificación muy antigua…»
- `hoteles_yes_5_12` real positivo → neutral: «Hotel situado en pleno centro de Madrid. Os explico. Este diciembre pasado fui a Madrid (en el puente de la immaculada) y estube mirando hotelitos por el centro. El que resultó más económico (y no es …»
- `hoteles_no_2_24` real negativo → neutral: «Hace tres años fui a Madrid con mis padres de vacaciones en agosto. No tenían pensado salir ese año ya_que normalmente solemos pasar las vacaciones en casaen mi casa no estamos acostumbrados a salir d…»
- `hoteles_no_2_9` real negativo → neutral: «Soy de Córdoba y en uno de mis viajes a Madrid pasé por la puerta de el hotel y su diseño me encantó, así que en mi siguiente viaje me alojé allí. La habitación me costó 280 € pillando una oferta. Rec…»

## 3. Cobertura frente a error

Se responde sin revisión humana solo si la confianza supera un umbral. El umbral se elige en `coah_val` como el más bajo con error ≤ 5%, y se informa en `coah_test`.

**Solo confianza** — umbral 0.85: en test se responde el **71%** de las reseñas con un error del **1.0%** (2 de 191); el 29% va a revisión.

| Umbral | Val: respondido | Val: error | Test: respondido | Test: error |
|---|---|---|---|---|
| 0.5 | 98% | 13.2% | 99% | 11.6% |
| 0.6 | 94% | 11.4% | 94% | 9.1% |
| 0.7 | 87% | 8.5% | 88% | 7.1% |
| 0.75 | 83% | 7.6% | 84% | 5.3% |
| 0.8 | 78% | 6.2% | 79% | 2.8% |
| 0.85 | 68% | 2.7% | 71% | 1.0% |
| 0.9 | 59% | 1.3% | 61% | 1.2% |
| 0.93 | 14% | 0.0% | 13% | 0.0% |
| 0.95 | 0% | 0.0% | 0% | 0.0% |
| 0.97 | 0% | 0.0% | 0% | 0.0% |
| 0.99 | 0% | 0.0% | 0% | 0.0% |

**Además, todas las negativas a revisión** — umbral 0.85: en test se responde el **47%** de las reseñas con un error del **0.8%** (1 de 126); el 53% va a revisión.

| Umbral | Val: respondido | Val: error | Test: respondido | Test: error |
|---|---|---|---|---|
| 0.5 | 68% | 13.1% | 70% | 12.3% |
| 0.6 | 65% | 11.4% | 65% | 9.7% |
| 0.7 | 61% | 9.8% | 62% | 7.8% |
| 0.75 | 58% | 8.3% | 58% | 5.1% |
| 0.8 | 55% | 7.4% | 55% | 3.4% |
| 0.85 | 46% | 3.2% | 47% | 0.8% |
| 0.9 | 39% | 1.9% | 40% | 0.9% |
| 0.93 | 14% | 0.0% | 13% | 0.0% |
| 0.95 | 0% | 0.0% | 0% | 0.0% |
| 0.97 | 0% | 0.0% | 0% | 0.0% |
| 0.99 | 0% | 0.0% | 0% | 0.0% |

