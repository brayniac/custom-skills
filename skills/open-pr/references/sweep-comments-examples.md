# Comment sweep examples

Genericised from real sweeps. Recognise the pattern, not the wording.

## Comments that did not survive

- `# Defaults to "primary" but honours SERVICE_ID from the environment` above
  the `os.environ.get` call. Derivable at the point of reading. What survived:
  which configuration layer wins when both are set, which comes from outside
  the function.
- A `Relaxed` ordering justified by "the lock's release/acquire edges already
  order these accesses" in a function that visibly holds the exclusive lock.
  Language semantics the reader owns; deleted.
- A type doc repeating the module doc's ownership protocol ("only the executor
  stores to it, between rounds, so the bound is fixed for one call"). The
  rationale was an echo and went. The requirement passed the retrieval test,
  because a store added anywhere else compiles and moves a bound out from
  under a reader, and stayed as one sentence.
- A four-line comment above a four-line classification function, paraphrasing
  its branches. Deleted.
- A layout comment justifying a mechanism "because auxiliary edges do not
  constrain placement" after auxiliary edges were removed. Rewritten to the
  current design.
- "After several failed attempts we discovered that the renderer ignores these
  edges during coordinate assignment." The constraint stayed as one sentence;
  the account of finding it went to the commit message.
- "Colours used to come from `--widget-*` tokens, which nothing defined; the
  alias tokens fixed that (PR #88)." Restated as "Colours come from the alias
  tokens; an undefined token renders the fallbacks." Both live facts kept.
- "This used to double-encode multibyte labels." Restated as a present-tense
  counterfactual: "Without the byte-length guard, multibyte labels
  double-encode."
- "The cast is safe — the SDK constructed the object, it simply doesn't
  declare the optionals strictly." Restated as the invariant: "The SDK
  constructs this object with every optional populated; the declared type is
  looser than the runtime guarantee."
- "A 64 KiB buffer should be enough for most cases." Restated as the bound and
  its failure: "64 KiB holds the largest observed frame (48 KiB); a larger
  frame fails in `decode`."

## The three false claims from step 5

- "The reverse direction is not testable yet: no producer attaches metadata to
  its stream." Four producers did, and a sibling test forwarded one. Corrected,
  and the claim became a second test.
- "The hosts that read this stream", over a list of hosts on which nothing read
  it. Rewritten as the forward-looking claim it was: hosts whose processes
  consume the stream's data by whatever transport carries it today; naming
  them stages the stream they will read once they move.
- "Metadata the real producer could have written", beside an `emit` that
  hardcoded the message kind and invented the source id. Either every field
  comes from the registry entry, or the claim goes.

## Trims that changed the claim

Enumerate the propositions (`write-technical-prose` step 4) before shortening.

| Original | Over-trimmed | Changed |
| --- | --- | --- |
| "These registrations are exceptions pending migration to slots." | "These registrations are sanctioned exceptions." | An obligation became an endorsement. |
| "A future IPC shell would subclass the executor." | "An IPC shell subclasses the executor." | A hypothetical became a shipped class. |
| "The notice narrates the check order; its text is also what `verify-doc` compiles against." | whole sentence deleted as narration | A real coupling went with the narration. Delete the clause, not the sentence. |
| "The 4 MiB ceiling is measured: the largest module is 3.1 MiB." | "The ceiling is 4 MiB; the largest module is 3.1 MiB." | Without "measured" the 3.1 MiB reads as a definition, and nobody re-measures. |
| "Nothing may be moved out of it here." | "Nothing moved out here." | A prohibition became a description of the present. |
