# Pollkadot

**US election results, county by county — sized by people, not acres.**

👉 **[pollkadot.zain.build](https://pollkadot.zain.build)**

A normal election map makes the country look mostly red because big, empty counties take up most of the space. Pollkadot lets you redraw the map so each county's size matches something that matters, like how many people live there or how many votes were cast. Then you can flip back to the regular map and watch it change.

---

## What you can explore

- **Races:** President, Senate, House and Governor, plus special elections. Tap the **year** or the **race** in the title at the top to switch.
- **Years:** President, Senate and Governor from 2000 to 2024, and the House from 2016 to 2024.
- **Counties or states:** look at every county, or merge them into states.

## The controls

The settings are a row of dropdowns along the top of the map. When they don't all fit, the row scrolls sideways: use the scroll wheel, drag it, or swipe.

| Control | What it does |
| --- | --- |
| **Size** | What each county's size represents: land area (a normal map), population, votes cast, electoral votes, Senate seats, college graduates or GDP. |
| **Rings** | Outlines that show what each county *would* look like under a second measure. For example, size by votes cast with rings for population shows where turnout is high or low. Pick **None** to hide them. |
| **Color** | **Share** shades each county by how much it leaned one way, from deep blue through purple to deep red. **Winner** colors each county by who won it. |
| **Show** | **Counties** or **States**. |
| **Borders** | **State borders** draws state outlines on top of circle maps. The contiguous shape always shows them. |

The first dropdown sets the map's **shape**:

- **Packed circles** (the default): each county becomes a circle sized by your measure, nudged apart so they don't overlap.
- **Circles in place:** circles stay right where the county is, so they overlap in crowded areas. Where they overlap, the colors blend based on how many votes each one has.
- **Contiguous:** the real county shapes are stretched and squeezed so their areas match your measure, while still fitting together like a map.

Other things you can do:

- **Hover** over a county or state for its numbers. On a phone, tap.
- **Click** a county to zoom in on it.
- **Zoom** with the scroll wheel or the **+ / −** buttons (bottom left), or pinch on a phone. **Drag** to move around.
- **Save** (the download button, top right) downloads a PNG of the whole map with your current settings. Zoom, hover and selections are left out.
- **Details** (top right) lists data sources and any gaps for the race you're looking at. It turns amber when something is missing.

### The curve in the corner

The curve in the bottom-right corner shows how counties are spread out from strongly Democratic to strongly Republican, weighted by your size measure.

- **Hover** the curve to see where you are.
- **Click and drag** to select a range, like "everywhere between D+10 and R+10". The rest of the map fades out. Selections snap to whole points, tenths, or exact county values.
- **Scroll** over the curve to zoom in, and right-drag to slide it.
- Press **Esc** or **✕** to clear the selection.

## Colors

Pollkadot uses only red and blue. A county split 50/50 is purple, and the colors in between are mixed so equal steps *look* equal (this uses a color space called OKLab). Third-party votes are counted in the totals but aren't shown as their own color.

## Where the data comes from

All numbers come from public sources and are processed the same way every time.

- **Election results:** MIT Election Data and Science Lab (county presidential returns and precinct returns), and Amlani & Algara's county returns for Senate and Governor races before 2016. Where those sources are missing a race or some counties, the gap is filled from the state's own official results, and **Details** says so.
- **Population:** US Census Bureau county estimates.
- **College graduates:** USDA Economic Research Service education data (Census 2000 and American Community Survey).
- **GDP:** US Bureau of Economic Analysis county GDP (from 2001; the 2000 maps use 2001).
- **County shapes:** US Census Bureau county boundaries.

## Things to know

- **Alaska** doesn't report results by borough, so it's shown as one statewide result.
- **Connecticut** uses its 8 historical counties.
- **House** results are added up by county across districts, so a county can include more than one race.
- Uncontested House races leave some counties blank, and a few older races have small gaps. **Details** lists them.
- A map with sizes this distorted can't be perfect. The contiguous shapes come within a few percent of the target sizes, and small counties may look a bit off.

---

Want to build or change Pollkadot? See [DEVELOPMENT.md](DEVELOPMENT.md).
