# Mirrored-evidence fixture

This directory contains a fictional, offline evaluation fixture. It must not be
treated as evidence about any real company, laboratory, or product.

The candidate-source files deliberately test whether a researcher recognizes
that multiple hostnames can reproduce one underlying press release. Run the
`adversarial-mirrored-evidence` case with access to the four files in
`sources/`. Keep `ground-truth.json` for the evaluator; do not provide it to the
research mode being scored.

The expected conclusion is not that the product claim is false. It is that the
available material does not independently verify it.
