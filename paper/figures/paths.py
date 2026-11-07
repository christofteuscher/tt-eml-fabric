"""Input locations for the figure scripts.

REPO  the tt-eml-fabric repository (sim/, spice/).  Found as the parent of
      this directory when the scripts sit in the repository's paper/figures/,
      or as ../../code/tt-eml-fabric from the paper source; EML_REPO overrides.
PAPER the paper source, which holds the simulation records POWER.md and
      FAB_SPICE.md and the manuscript.  These are not public; set EML_PAPER to
      a copy of the paper source to run Figs. 1, 5 and 6.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def _first(env, candidates, probe):
    if os.environ.get(env):
        return os.path.abspath(os.environ[env])
    for c in candidates:
        if os.path.exists(os.path.join(c, probe)):
            return os.path.abspath(c)
    return None


REPO = _first("EML_REPO", [os.path.join(HERE, "..", ".."),
                           os.path.join(HERE, "..", "..", "code", "tt-eml-fabric")],
              os.path.join("sim", "eml_fabric_topo.py"))
PAPER = _first("EML_PAPER", [os.path.join(HERE, "..")], "POWER.md")


def repo(*p):
    if REPO is None:
        raise SystemExit("tt-eml-fabric repository not found; set EML_REPO")
    return os.path.join(REPO, *p)


def paper(*p):
    if PAPER is None:
        raise SystemExit("this figure reads files of the paper source "
                         "(%s), which are not public; set EML_PAPER" % "/".join(p))
    return os.path.join(PAPER, *p)


def corpus_stats(mode="exact"):
    name = "corpus_stats_%s.json" % mode
    for c in (os.path.join(HERE, name), repo("sim", "corpus", name)):
        if os.path.exists(c):
            return c
    raise SystemExit(name + " not found; run corpus_enum.py " + mode)
