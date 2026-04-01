# PMF Action Plan — Field Genius

> Basado en la auditoria de producto del 2026-04-01 (PMF score 4.5/10)
> Objetivo: subir a 7+/10 antes del piloto con Telecable

---

## Acciones inmediatas (antes del demo)

### 1. Demo telecom-specific (no laundry care)
- [ ] Tomar 10-15 fotos reales de puntos de venta de telecomunicaciones en CO/CR
  - Tiendas propias Claro, Movistar
  - Distribuidores autorizados
  - Material POP en calle
  - Instalaciones de cable/internet
- [ ] Crear sesion demo con esas fotos via WhatsApp
- [ ] Generar los 3 reportes (competidor, cliente, comunicacion) y validar calidad
- [ ] Ajustar prompts basado en los resultados

### 2. Definir 3 metricas de ROI con Telecable
Propuestas:
1. **Amenazas detectadas**: "Detectamos X amenazas competitivas que no estaban en su radar"
2. **Tiempo ahorrado**: "Reducimos el procesamiento de reportes de campo de 2h/dia a 10min"
3. **Cobertura**: "Cubrimos X% mas zonas que el sistema manual actual"

### 3. Preparar objeciones del comprador
| Objecion | Respuesta |
|----------|-----------|
| "Mis agentes no van a usar WhatsApp para esto" | "No necesitan aprender nada nuevo — ya usan WhatsApp. Solo envian fotos como lo hacen normalmente." |
| "Puedo hacer esto con ChatGPT" | "ChatGPT analiza 1 foto a la vez. Nosotros consolidamos 1,000 reportes diarios en inteligencia accionable por zona." |
| "$96K/ano es mucho" | "Un analista dedicado cuesta $36K/ano y procesa 10% de lo que nuestro sistema hace automaticamente." |
| "Y si la AI se equivoca?" | "Cada reporte tiene confidence score + content moderation. Los datos dudosos se marcan, no se ocultan." |
| "Quiero probarlo antes de pagar" | "Piloto de 30 dias con 50 usuarios a $2,500/mes. Si no genera valor, no hay compromiso." |

### 4. Estructura del contrato
```
PILOTO (30 dias):
- 50 usuarios
- $2,500/mes
- $5,500 setup (pagado al inicio)
- Sin compromiso de permanencia post-piloto

ESCALAMIENTO (si piloto exitoso):
- 12 meses minimo
- 3 meses de aviso para cancelar
- Pricing por tier (100/500/1000 usuarios)
- Revisión de precio anual
```

### 5. Valor inmediato para el agente de campo
El agente es quien captura pero no recibe beneficio directo. Ideas:
- **Auto-reporte diario**: Al final del dia, el agente recibe un resumen de sus visitas ("Hoy visitaste 5 puntos, capturaste 23 fotos, detectaste 2 amenazas competitivas")
- **Ranking semanal**: "Eres el #3 de tu zona esta semana en capturas"
- **Alertas cruzadas**: "Otro agente detecto que Claro esta ofreciendo 3 meses gratis en tu zona"

### 6. Competitive teardown pendiente
- [ ] Registrarse en GoSpotCheck (FORM by Aforza) trial
- [ ] Registrarse en Repsly trial
- [ ] Documentar: que hacen que nosotros no?
- [ ] Documentar: que hacemos que ellos no? (WhatsApp-native, multi-framework AI)

---

## Pricing validado por modelo de costos

| Tier | Usuarios | Precio/mes | AI cost (Haiku) | Infra | Margin |
|------|----------|-----------|-----------------|-------|--------|
| Starter | 100 | $2,500 | $256 | $130 | 85% |
| Growth | 500 | $6,000 | $900 | $150 | 82% |
| Enterprise | 1,000 | $8,000 | $2,580 | $170 | 66% |

**Critical**: estos numeros asumen Vision con Haiku (ya implementado). Con Sonnet, el margen del tier Enterprise cae a 5%.

---

## Metricas de exito del piloto

| Semana | KPI | Target |
|--------|-----|--------|
| 1 | Usuarios que enviaron al menos 1 foto | >= 40 de 50 (80%) |
| 2 | Promedio fotos por usuario activo | >= 3/dia |
| 3 | Reportes generados por gerentes | >= 10 reportes de grupo |
| 4 | Rating de calidad por gerentes | >= 3.5/5 |
| 4 | Amenazas detectadas | >= 5 |
| 4 | Decision go/no-go para escalamiento | Si/No |

---

## Dependencias de Telecable (acciones del cliente)

- [ ] Firmar contrato de piloto + pagar setup $5,500
- [ ] Aplicar a WhatsApp Cloud API (verificacion Business de Meta)
- [ ] Proveer lista de 50 usuarios piloto (CSV: phone, name, role, country, zone)
- [ ] Proveer lista de competidores por pais con planes/precios actuales
- [ ] Proveer lista de productos/servicios de Telecable por pais
- [ ] Designar 1 punto de contacto para feedback de calidad de reportes
- [ ] Designar gerente(s) que usaran el backoffice

---

## Riesgos mitigados por sprints completados

| Riesgo original (auditoria) | Sprint que lo mitigo | Estado |
|-----------------------------|---------------------|--------|
| 30+ endpoints sin auth | E-1 | DONE |
| Race condition data loss | E-2 | DONE |
| API sin versioning | E-3 | DONE |
| NSFW content sin filtrar | P-1 | DONE |
| PII en audio | P-1 | DONE |
| Vision con Sonnet (caro) | P-2 | DONE — Haiku |
| Sync client blocking | P-4 | DONE — async |
| No mobile responsive | P-3 | DONE |
| No retry en AI calls | P-4 | DONE |
| Whisper solo español | P-4 | DONE — auto-detect |

## Riesgos pendientes

| Riesgo | Mitigacion | Cuando |
|--------|-----------|--------|
| WhatsApp verification delay | Tener 360dialog como backup | Antes del piloto |
| Adopcion baja (< 50%) | Auto-reporte diario + ranking | Sprint futuro |
| Jorge = single point of failure | Documentar runbooks + contratar jr | Mes 3 |
| AI costs higher than projected | Monitor con usage tracking + caps | Continuo |
