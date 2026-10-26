# Solar System — Population Globe

A single-file, offline solar system viewer in `index.html` (WebGL, no
libraries). The Sun, all eight planets and 14 of the 15 moons are wrapped
with real NASA-based photographic maps (Solar System Scope, CC-BY 4.0,
embedded in the HTML as data URIs so the page works when opened straight
from disk; Nereid alone has no global map and stays procedural). Planets
follow true Kepler ellipses with real tilts and spin rates, compressed in
time; every planet carries its notable moons.

Two extra vantage points:

* **Moon view** — while Earth is focused, press *View from the Moon*: the
  camera parks on the lunar surface, holding the Earth at ~30° width above
  a ray-traced horizon.
* **Moons inset** — on any focused planet, press *View the moons*: one live
  close-up window per moon appears in the top-right, on a shared scale.

## Run

Double-click `index.html`, or open it in any modern browser.

## Controls

| Action | Result |
| --- | --- |
| Drag / Scroll | Rotate / zoom |
| Hover | Orbit highlight + size tooltip; motion pauses |
| Click a planet | Smoothly focus it and follow |
| Click the Sun / empty space | Return to the overview |
| **View the moons** | One live window per moon, top-right |
| **View from the Moon** | Fixed vantage on the lunar surface |
| `← Back to Earth` / `Esc` | Leave the Moon view → Earth's orbit view |
| **Open population globe** | Zoom into the embedded Earth Population Globe |
| `← Back to Earth` / `Esc` inside the globe | Close it → Earth's orbit view |
| `Esc` in orbit view | Smoothly back to the whole-system overview |
| `I` | Toggle real inclinations ↔ ×4 exaggeration |
| `R` / `P` inside the globe | Reset camera / switch physical ↔ digital |

## Notes

* Sizes and orbit spacing are stylized for visibility; orbital shapes,
  tilts, inclinations and spins are real.
* Maps are embedded as base64 data URIs because browsers reject local
  `file://` images in WebGL textures — this keeps the single file fully
  offline. Loose copies live in `maps/` (including `saturnring.png`, kept
  for a possible textured ring).
* Moon map sources: Solar System Scope (CC-BY 4.0); Phobos/Deimos from
  NASA PDS Stooke maps (CC-BY 3.0); Proteus from NASA/JPL Voyager 2
  imagery; Titan from NASA PIA22770. Titania/Oberon fill the never-imaged
  hemisphere with a continuing from their real half; Nereid is procedural
  by design.
* The render loop is allocation-free and steps down internal resolution
  automatically if frames are dropped.
* `earth-globe/index.html` is a snapshot copy of the Earth Population
  Globe app; the README there documents the globe itself.
