# Rendering the new wave paper

The new utilities are separate from the retained original manuscript, renderer and submitted PDF. They read aggregate results and an explicitly supplied Markdown manuscript. They do not alter analysis inputs or select individual study cases.

## Runtime and font assets

Use Python with ReportLab, Mistune 3, Matplotlib, pypdf and Pillow. In the Codex task, use its bundled Python interpreter; the utilities can also use the already available task-local package directory when a library is absent from that interpreter. No model service, API key or authentication is involved in rendering.

The three unmodified Old Standard TT fonts come from the [official Google Fonts family directory](https://github.com/google/fonts/tree/main/ofl/oldstandardtt). Its [SIL Open Font License 1.1](https://github.com/google/fonts/blob/main/ofl/oldstandardtt/OFL.txt) permits embedding and distribution with the included copyright/license. The license does not attach to documents produced with the font. Retain `assets/fonts/old-standard-tt/OFL.txt` and the source manifest when distributing the font files.

Old Standard TT has no Greek kappa or capital Delta glyph in this distribution. The renderer uses an explicit embedded DejaVu Serif fallback for unsupported scientific glyphs, while regular, bold and italic document text retains the template family. An uncovered glyph causes an error instead of an invisible replacement.

## Figure 1

```text
python src/newwave_figures.py --machine results/newwave_machine_aggregate.json --browser results/newwave_browser_aggregate_with_recode.json --output-dir output/figures
```

This creates `newwave_access_figure1.pdf`, a 400-dpi PNG, a numbered caption and a hash manifest. The figure is exactly 6.5 inches wide. Panel A contains machine census values, with the expectation for one uniformly chosen distinct citation kept separate from any-citation availability. Panel B distinguishes group unresolved-content bounds, the paired identified set and the outer 95% design interval. The identified set is not plotted or described as an ordinary confidence interval. No support-sample funnel is used.

## Manuscript layout

```text
python src/render_newwave_report.py --sourceMD report_newwave.md --outputPDF output/pdf/Community_Notes_Newwave.pdf --figure output/figures/newwave_access_figure1.png
```

Start with `# Title`, then an author paragraph and affiliation paragraph, then `## Abstract`. The renderer retains the title/author/With Apart Research hierarchy. The abstract must be 150-250 words. Place `<!-- PAGEBREAK -->` or `[[PAGEBREAK]]` between the four planned main pages. References and Appendix headings start separate pages automatically. The default main-page check requires exactly four pages before those sections; `--main-pages 0` disables that count only for layout diagnosis.

Insert `[[FIGURE1]]` to load the selected figure and generated caption. An immediately following paragraph beginning `Figure 1.` overrides the generated caption. Standard Markdown image paths with numbered captions also work. Tables automatically fit the 468-point content frame and repeat their header when needed. Inline code, Markdown links, p~a~ subscripts, p^2^ superscripts, explicit HTML sub/sup tags and simple inline math such as `$N_h/n_h$` are supported. Unsupported TeX is rejected rather than printed as raw notation.

The page is US Letter with exactly one-inch margins and zero hidden frame padding. Body text is 11 points with 15-point leading; the title is 20-point bold and major headings 14-point bold. Table/caption text remains readable at 9.5 points. Output metadata derives its title and author from the manuscript. The retained original PDF filename is protected, and a page-count failure does not replace an existing valid output.

## Final quality gate

The layout smoke test is an intermediate artifact, not the final paper. After every final manuscript edit, render again, convert every PDF page to PNG with Poppler, and inspect all pages at full resolution. Check page count, title/author block, paragraph breaks, tables, figure caption, scientific glyphs, links, references and appendix transitions. The generated manifest is an arithmetic/layout record; visual inspection remains required.
