# Pollkadot

**US election results, county by county — sized by people, not acres.**

👉 **[pollkadot.zain.build](https://pollkadot.zain.build)**

A normal election map makes the country look mostly red because big, empty counties take up most of the space. Pollkadot lets you redraw the map so each county's size matches something that matters, like how many people live there or how many votes were cast. Then you can flip back to the regular map and watch it change.

---

## What you can explore

- **Races:** President, Senate, House and Governor, plus special elections. Tap the **year** or the **race** in the title at the top to switch.
- **Years:** presidential elections from 2008 to 2024, and Senate, House and Governor races from 2016 to 2024.
- **Counties or states:** look at every county, or merge them into states.

## The controls

The four controls at the bottom of the map:

| Control | What it does |
| --- | --- |
| **Size** | What each county's size represents: land area (a normal map), population, votes cast, electoral votes, Senate seats, college graduates or GDP. |
| **Rings** | Outlines that show what each county *would* look like under a second measure. For example, size by votes cast with rings for population shows where turnout is high or low. Pick **None** to hide them. |
| **Color** | **Share** shades each county by how much it leaned one way, from deep blue through purple to deep red. **Winner** colors each county by who won it. |
| **Show** | **Counties** or **States**. |

**Shape** sets how the map is drawn:

- **Packed circles** (the default): each county becomes a circle sized by your measure, nudged apart so they don't overlap.
- **Circles in place:** circles stay right where the county is, so they overlap in crowded areas. Where they overlap, the colors blend based on how many votes each one has.
- **Contiguous:** the real county shapes are stretched and squeezed so their areas match your measure, while still fitting together like a map.

Other things you can do:

- **Hover** over a county or state for its numbers. On a phone, tap.
- **Click** a county to zoom in on it.
- **Zoom** with the scroll wheel or the **+ / −** buttons. **Drag** to move around.
- **State borders** draws state outlines on top of circle maps.
- **Save** downloads a PNG of the whole map with your current settings. Zoom, hover and selections are left out.
- **Details** (top right) lists data sources and any gaps for the race you're looking at. It turns amber when something is missing.

### The curve under the map

The curve at the bottom shows how counties are spread out from strongly Democratic to strongly Republican, weighted by your size measure.

- **Hover** the curve to see where you are.
- **Click and drag** to select a range, like "everywhere between D+10 and R+10". The rest of the map fades out. Selections snap to whole points, tenths, or exact county values.
- **Scroll** over the curve to zoom in, and right-drag to slide it.
- Press **Esc** or **✕** to clear the selection.

## Colors

Pollkadot uses only red and blue. A county split 50/50 is purple, and the colors in between are mixed so equal steps *look* equal (this uses a color space called OKLab). Third-party votes are counted in the totals but aren't shown as their own color.

## Where the data comes from

All numbers come from public sources and are processed the same way every time.

- **Election results:** MIT Election Data and Science Lab (county and precinct returns), and Tony McGovern's county-level presidential results for 2020 and 2024.
- **Population:** US Census Bureau county estimates.
- **College graduates:** USDA Economic Research Service education data.
- **GDP:** US Bureau of Economic Analysis county GDP.
- **County shapes:** US Census Bureau county boundaries.

## Things to know

- **Alaska** doesn't report results by borough, so it's shown as one statewide result.
- **Connecticut** uses its 8 historical counties.
- **House** results are added up by county across districts, so a county can include more than one race.
- Uncontested races and missing reports leave some counties blank. **Details** lists them.
- A map with sizes this distorted can't be perfect. The contiguous shapes come within a few percent of the target sizes, and small counties may look a bit off.

---

Want to build or change Pollkadot? See [DEVELOPMENT.md](DEVELOPMENT.md).
