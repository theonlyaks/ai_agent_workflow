# WF004_sku_lookup

_What this checks: Attributes are filled from the catalog by SKU; missing attributes are marked, not invented_

**Request:** Write SEO content for SKU-2004

**Selected Workflow:** WF004 - Product Description Generator
**Routing:** Claude tool calling (confidence: high) - User wants SEO product content (description, SEO title, meta) for a specific SKU.
**Status:** ✅ Completed

### Steps Executed
1. ✅ **Validate required attributes** [`enrich_from_table`, `validate_fields`] - Matched reference record SKU-2004; filled: product_name, category, material, color → All required fields present (5 provided)
2. ✅ **Create product description** [`llm_generate`] - Generated description (claude-sonnet-5-5)
3. ✅ **Generate short description** [`llm_generate`, `validate_text`] - Generated short_description (claude-sonnet-5-5) → short description: 176 chars - OK
4. ✅ **Generate SEO title** [`llm_generate`, `validate_text`] - Generated seo_title (claude-sonnet-5-5) → seo title: 52 chars - OK
5. ✅ **Generate meta description** [`llm_generate`, `validate_text`, `build_record`] - Generated meta_description (claude-sonnet-5-5) → meta description: 152 chars - OK

### Result
The SEO content for **SKU-2004 (Chelsea Boots)** is ready: a product description, a short description, an SEO title ("Chelsea Boots in Dark Brown Suede | Classic Footwear"), and a meta description. It is based on the product name, category (Footwear), material (suede) and color (dark brown). Note that attributes and target audience were not provided, so they were marked as missing rather than invented. If you can supply them, the content could be refined to reflect them.

#### Generated product content

- **Product:** Chelsea Boots
- **Sku:** SKU-2004
- **Product description:** Meet the Chelsea Boots, a classic piece of footwear made from suede in a rich dark brown shade. The soft, textured finish of suede gives these boots a warm, refined look that feels both timeless and easy to appreciate. Dark brown is a versatile tone, making it simple to pair the boots with a wide range of outfits, from relaxed everyday looks to smarter combinations.  The Chelsea boot silhouette has long been a wardrobe staple, valued for its clean lines and understated character. Crafted in suede, this pair brings depth and texture to your style without trying too hard. Whether you are updating your footwear collection or looking for a dependable pair to wear again and again, the Chelsea Boots in dark brown suede offer a stylish, versatile choice.
- **Short description:** Classic Chelsea Boots in dark brown suede. The soft, textured finish adds warmth and depth to your look, and the versatile shade pairs easily with everyday and smarter outfits.
- **Seo title:** Chelsea Boots in Dark Brown Suede \| Classic Footwear
- **Meta description:** Discover the Chelsea Boots in dark brown suede, a timeless footwear staple with a soft, textured finish. Explore the look and find your next go-to pair.
- **Missing information:**
  - attributes
  - target_audience

#### Product facts used

- **Provided:**
  - **Product name:** Chelsea Boots
  - **Sku:** SKU-2004
  - **Category:** Footwear
  - **Material:** Suede
  - **Color:** Dark brown
- **Missing required:** _none_
- **Missing recommended:**
  - attributes
  - target_audience

**Warnings:**
- Not provided (marked as missing, not invented): attributes and target audience

_Run run-20261014-185110-0cfabb - 12.5s, LLM calls: 6, tokens: 9414 in / 734 out_
