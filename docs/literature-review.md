# Engineering engine and SHM literature notes

This is a curated starting bibliography for architectural and calculation choices. It spans foundational mechanics, established SHM methods, and newer digital-twin and automated-identification work. A paper's existence does not mean its algorithm is implemented or validated by Timoshenko.

## Mechanics and beam formulations

- Euler's 18th-century elastic column stability result provides the classical slender-column eigenvalue baseline; Timoshenko later broadened elementary beam bending to include shear deformation. The package implements only the named ideal Euler expression, not inelastic/design-code column curves.
- Timoshenko's historical shear-deformation beam work established a correction to elementary beam theory; historical record: [On the Correction for Shear of the Differential Equation for Transverse Vibrations of Prismatic Bars (1921)](https://doi.org/10.1080/14786442108636264).
- Saint-Venant torsion is a foundational elasticity problem; circular shafts have the simple `T/J` stress relation, while arbitrary sections require warping/stress-function treatment. A modern paper derives energy-based shear/torsion factors for rods ([2009 preprint](https://arxiv.org/abs/0912.2622)); a recent 2025 paper applies physics-informed networks to the more general Saint-Venant torsion field ([2025 preprint](https://arxiv.org/abs/2505.12389)). Neither non-circular torsion method is implemented.
- Cowper examined accuracy/definitions for Timoshenko beam theory ([1966](https://doi.org/10.1061/JMCEA3.0001048)). This supports treating shear correction and deflection conventions explicitly rather than presenting a universal coefficient as exact.
- Closed-form relationships between Timoshenko and Euler–Bernoulli beam solutions were presented for single-span cases ([1995](https://doi.org/10.1061/%28ASCE%290733-9399%281995%29121%3A6%28763%29)).
- A later unified treatment discusses shear-coefficient formulations ([2017](https://doi.org/10.1061/%28ASCE%29EM.1943-7889.0001297)).
- Von Mises' 1913 criterion underlies the plane-stress equivalent stress formula. This API computes the mathematical equivalent stress, but does not compare it with yield strength or state whether yielding occurs. NASA's later structural-analysis documentation discusses plane-stress von Mises formulations ([NASA technical report](https://ntrs.nasa.gov/api/citations/19750015682/downloads/19750015682.pdf)).
- Classical pressure-vessel membrane equations apply only in a thin-wall regime away from discontinuities. A 2015 review explicitly compares the applicability of common elastic hoop-stress formulas ([Reliability Engineering & System Safety, ScienceDirect](https://www.sciencedirect.com/science/article/pii/S0308016115000071)); a 2021 study examines stress measurements in thin-wall pressurized vessels ([Materials Research, DOI: 10.1590/1980-5373-MR-2021-0495](https://doi.org/10.1590/1980-5373-MR-2021-0495)).

## Structural health monitoring and modal identification

- Farrar and Worden frame SHM as a statistical pattern-recognition problem and discuss operational/environmental variability ([2007](https://doi.org/10.1098/rsta.2006.1928)). This motivates returning evidence and quality rather than equating one changed frequency with damage.
- Brincker, Zhang and Andersen introduced frequency-domain decomposition as output-only modal identification ([2001](https://doi.org/10.1088/0964-1726/10/3/303)).
- Mottershead and Friswell survey structural dynamic model updating and its parameterization/identification challenges ([1993](https://doi.org/10.1006/jsvi.1993.1340)). A one-factor stiffness scaling is therefore documented as a narrow baseline, not general model updating.
- A 2024 review summarizes modal parameter recognition and damage identification under environmental excitation ([DOI: 10.32604/sdhm.2024.053662](https://doi.org/10.32604/sdhm.2024.053662)).
- A 2024 automated output-only identification paper combines frequency-domain methods with MAC to identify frequencies and mode shapes ([Engineering Structures, DOI: 10.1016/j.engstruct.2024.119210](https://doi.org/10.1016/j.engstruct.2024.119210)). This is a later direction; current 0.4 FDD does not implement MAC-based pairing or SSI stabilization diagrams.

## Digital twins and infrastructure interoperability

- A civil-infrastructure digital-twin review surveys work from 2005–2024, including sensing, data/model integration, platforms, use cases, and persistent challenges ([2024 review, PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC11723349/)). The practical architectural implication is to make the asset model, observations, and integrations explicit and separate rather than hiding project-specific assumptions in the analysis core.
- The [OGC SensorThings API standard](https://www.ogc.org/standards/sensorthings/) provides an interoperable vocabulary for things, sensors, datastreams, and observations. Timoshenko does not claim conformance in 0.4; it remains a candidate adapter target.
- The [buildingSMART IFC standards](https://standards.buildingsmart.org/) and [OPC Foundation specifications](https://reference.opcfoundation.org/) are candidate exchange/streaming boundaries for future optional adapters, not core dependencies.

## Message transport and Python extension packaging

- The [OASIS MQTT 5.0 standard](https://docs.oasis-open.org/mqtt/mqtt/v5.0/mqtt-v5.0.html) defines QoS delivery levels, retained publications, session expiry, and packet acknowledgement. Timoshenko's MQTT adapter uses application-level source/batch IDs because transport message IDs are not durable project provenance; it defaults to skipping retained samples and acknowledges QoS 1/2 only after session ingestion.
- The [Eclipse Paho Python client API](https://eclipse.dev/paho/files/paho.mqtt.python/html/client.html) separates the connection, network loop, subscriptions, callbacks, and disconnect lifecycle. Its [callback migration guide](https://eclipse.dev/paho/files/paho.mqtt.python/html/migrations.html) documents the callback API versioning introduced in Paho 2.x. The optional adapter uses API v2 and keeps the Paho import outside the core import path.
- Paho's published [known limitations](https://pypi.org/project/paho-mqtt/) state that client-side session state is in memory rather than restored after process restart. Persistent broker sessions therefore do not alone guarantee process-restart recovery; SQLite batch history and explicit operational replay remain necessary.
- The [Python Packaging User Guide](https://packaging.python.org/en/latest/specifications/declaring-project-metadata/) specifies `optional-dependencies` as per-extra PEP 508 requirements. Timoshenko uses the `mqtt` extra to avoid making Paho a core dependency.

## Time-varying environmental effects

- SHM on real bridges requires separating operational/environmental effects from structural change. A recent 2026 bridge study models temperature-dependent frequencies for a particular sample of prestressed concrete bridges ([Pivetta et al., Engineering Structures, DOI: 10.1016/j.engstruct.2026.122664](https://doi.org/10.1016/j.engstruct.2026.122664)). Its bridge type, data range, and calibration are specific; it is not a universal temperature-correction equation to put in a general engine.
- Environmental/operational variability normalization and statistical treatment remain an active area; methods should be selected and calibrated against the asset and its operating regime. Timoshenko therefore exposes generic thermal strain as an elementary mechanics calculation, while leaving frequency-vs-temperature baselines to a later calibrated SHM layer.

## Engine architecture patterns consulted

The roadmap's architecture comparison links the official Godot engine architecture and lifecycle, Unreal subsystems, FastAPI modular routers, Temporal workflow/worker separation, Azure Digital Twins graph/model concepts, OGC observation vocabulary, OPC UA PubSub, IFC, and Python packaging/entry-point specifications. These references informed narrow module boundaries, optional adapters, explicit lifecycle and package import conventions. Timoshenko is not copying the runtime model of any one engine.
