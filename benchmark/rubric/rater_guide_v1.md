# Rater guide, version 1

> **DRAFT, for the owner's review (2026-10-13).** Written before any rater has used it; expect
> changes after the first calibration round. Codes and definitions: [rubric_v1.md](rubric_v1.md)
> (human-readable) and [rubric_v1.yaml](rubric_v1.yaml) (what the tools use).

## Your task

You will receive a **packet**: one HTML file that opens in any browser, with no internet
connection or account needed. It shows, for each rewritten paragraph:

- the **source paragraph** from the paper (left), with the rest of the source passage available;
- the **rewritten paragraph** (right), with any **marked additions** highlighted;
- the rewritten paragraph's **claims**, one per row, each with the rubric's questions.

Answer every question for every claim, then the one paragraph-level question. Your answers are
saved in the browser as you go. When you finish, press **Export ratings** and send the downloaded
JSON file back. You do not see which model or person wrote a rewrite, and you should not try to
find out.

## General rules

1. **Judge against the source, not against your own knowledge**, except for
   `added_information`, which asks whether added content is correct.
2. **Each code is separate.** Do not let one answer decide another. A claim can be `supported` and
   still lose a hedge; a marked addition is usually `unsupported` and then classified by
   `added_information`.
3. **Read the whole source paragraph first**, then the rewritten paragraph, then the claims.
4. **When in doubt, choose the more conservative reading of the source** (the one with the hedges
   and limits in it), and write a short comment. Comments are read during adjudication.
5. **Spin or overstatement already in the source is not the rewrite's fault.** If the source
   overclaims and the rewrite repeats it faithfully, code no, and say so in a comment.
6. Simplified vocabulary is expected and fine. "Lifespan increased by 12%" and "the mice lived
   about an eighth longer" say the same thing.

## Worked examples

> **ILLUSTRATIVE ONLY.** The source paragraphs below are quoted verbatim from a real CC BY 4.0
> article (attribution under each). Every "claim" below was **written by hand for this guide** to
> demonstrate one code. None is model output, none comes from a real rewrite, and nothing here is
> a rating of any real system.

### Source A

> ES-62 is a 62 kDa glycoprotein found in the excretory secretory products of the filarial
> nematode parasite A. viteae with anti-inflammatory properties. In the first study of its kind,
> Crowe et al., 2020 reported that weekly administration of ES-62 improved late-life health and
> increased lifespan (+12%, median lifespan) in a C57BL/6J mouse model of high-calorie
> diet-accelerated aging. This suggests that the anti-inflammatory capacities of helminth therapy
> can exert protective effects even in later life.

*Zhang B, Gems D. "Gross ways to live long: Parasitic worms as an anti-inflammaging therapy?"
eLife 2021;10:e65180, doi:10.7554/eLife.65180, paragraph `sec1.2-p2`. © 2021 Zhang and Gems,
CC BY 4.0 (<https://creativecommons.org/licenses/by/4.0/>). Quoted unchanged from the PMC copy
committed as a test fixture (`libs/rbcore/tests/fixtures/jats/elife-65180-pmc-s3.xml`).*

| Illustrative claim | Codes (every code not listed is "no", and `support` is "supported" unless listed) | Why |
|---|---|---|
| "In a 2020 study, mice given ES-62 every week lived about 12% longer on average." | none | Same population, dose schedule and effect, plainly worded. ("Median" simplified to "on average" is borderline; a careful rater would comment.) |
| "ES-62 makes animals live longer." | `overgen_generic` = yes; `overgen_present_tense` = yes | One mouse model becomes "animals"; "increased" becomes the timeless "makes ... live longer". |
| "Older people could take ES-62 to stay healthy for longer." | `overgen_action_guiding` = yes; `support` = unsupported | A mouse result becomes advice for people. |
| "The study proves that worm therapy protects against ageing." | `lost_hedge` = yes; `spin` = yes | "Suggests" becomes "proves"; one first study becomes proof. |
| "Mice given ES-62 every day lived 21% longer." | `substituted_detail` = yes; `support` = contradicted | Weekly becomes daily and +12% becomes 21%. |
| "ES-62 comes from a parasitic worm." (inside a marked addition) | `support` = supported; `added_information` = no | The source says so ("filarial nematode parasite"), so nothing was added even though it was marked. |
| "Nematodes are roundworms." (inside a marked addition) | `support` = unsupported; `added_information` = factual | Correct background the source does not state. |
| "ES-62 is already approved as a medicine." | `support` = unsupported; `added_information` = non_factual | Not in the source and presented as fact without basis. Unmarked additions like this are exactly what the marking rule is meant to surface. |

### Source B

> A prediction of the ‘anti-inflammaging helminth hypothesis’ is that in areas endemic for helminth
> infection, there should be lower rates of inflammaging-related disease, and there is some
> evidence for this. For example, in a region of Eastern India endemic for lymphatic filariasis
> infection, it was found that not one of 207 rheumatoid arthritis patients tested positive for
> circulating filarial nematode antigens; by contrast, 40% of 222 healthy controls were antigen
> positive (Panda et al., 2013). This is consistent with a protective role of helminth infection
> against rheumatoid arthritis. [...]

*Same article, paragraph `sec1.2-p7` (first three sentences shown). CC BY 4.0.*

| Illustrative claim | Codes | Why |
|---|---|---|
| "In one region of India, none of 207 people with rheumatoid arthritis carried signs of the worm infection, compared with 40% of 222 healthy people." | none | Faithful. |
| "Worm infections prevent rheumatoid arthritis." | `correlation_to_causation` = yes; `lost_hedge` = yes; `overgen_generic` = yes | An association in one population ("consistent with") becomes a general causal fact. |
| "People with worm infections are less likely to have rheumatoid arthritis, at least in this part of India." | none | Keeps the association and the population limit. |

### Source C (paragraph-level code)

> There is also some very limited evidence that helminth therapy might promote resistance to some
> forms of cancer. The tapeworm Taenia crassiceps and its antigens have been found to attenuate
> and prevent colon tumorigenesis in mice through anti-inflammatory mechanisms (León-Cabrera et
> al., 2014; Callejas et al., 2019). However, in the same mouse model, the nematode H. polygyrus
> was found to promote tumorigenesis (Pastille et al., 2017). Moreover, certain parasitic
> helminths are well known to increase cancer rates, for example the trematode parasite
> Schistosoma haematobium causes bladder cancer (Vennervald and Polman, 2009).

*Same article, paragraph `sec1.2-p9`. CC BY 4.0.*

Illustrative rewritten paragraph: "A tapeworm and substances from it have protected mice against
bowel cancer, so worm therapy may help prevent some cancers."

- `dropped_limitation` = **yes**: the contrary mouse result (H. polygyrus promoted tumours) and
  the known cancer-causing parasite are both gone, and "very limited evidence" is reduced to "may".
- At claim level, "worm therapy may help prevent some cancers" keeps a hedge (`lost_hedge` = no)
  but its emphasis on benefit alone, once the harms are dropped, is a candidate for `spin` = yes.
  Raters may reasonably differ here; that is what the comment field and adjudication are for.

## The codes in brief

| Code | Unit | Answer yes (or the named value) when |
|---|---|---|
| `support` | claim | supported: the source states or entails it; unsupported: the source does not say it; contradicted: the source says otherwise |
| `overgen_generic` | claim | a limited finding ("in 62% of", "in this cohort") becomes generic |
| `overgen_present_tense` | claim | "reduced" becomes "reduces": a past finding stated as a timeless truth |
| `overgen_action_guiding` | claim | a description becomes advice about what to do |
| `overgeneralisation` | claim | derived automatically: any of the three shifts above |
| `lost_hedge` | claim | the claim is more certain than the source |
| `correlation_to_causation` | claim | an association is stated as cause and effect |
| `spin` | claim | the finding is made to look more favourable, important or conclusive |
| `substituted_detail` | claim | a number, unit, population, intervention, comparator or outcome changed |
| `added_information` | claim | factual: correct added background; non_factual: wrong or unverifiable added content |
| `dropped_limitation` | paragraph | a limitation or caveat in the source paragraph is missing from the rewrite |

## Practical notes

- Budget about 30–45 seconds per claim once you are familiar with the rubric; a rewrite has about
  20–30 claims.
- If a claim is garbled or not a claim at all (a fragment from splitting), rate it as well as you
  can and say so in the comment; the decomposition is checked too.
- Ratings are pseudonymous: your packet carries a rater ID, not your name.
- Do not discuss specific items with the other rater until both of you have exported; agreement
  is only meaningful if the ratings are independent.
