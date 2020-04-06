import subprocess
from pathlib import Path

import atomium

from structuralalignment.superposition.base import CommandLineWrapper
from structuralalignment.utils import enter_temp_directory


"""
Theseus superposes a set of macromolecular structures simultaneously
using the method of maximum like-lihood (ML), rather than the
conventional least-squares criterion. Theseus assumes that the
structures are distributed according to a matrix Gaussian
distribution and that the eigenvalues of the atomic
covariancematrix are hierarchically distributed according
to an inverse gamma distribution. This ML superpositioning model
produces much more accurate results by essentially downweighting
variable regions of the structuresand by correcting for correlations
among atoms.

References
----------
* https://theobald.brandeis.edu/theseus/
* Optimal simultaneous superpositioning of multiple structures with missing data.
  Theobald, Douglas L. & Steindel, Philip A. (2012) Bioinformatics 28 (15): 1972-1979
* Accurate structural correlations from maximum likelihood superpositions.
  Theobald, Douglas L. & Wuttke, Deborah S. (2008) PLOS Computational Biology 4(2):e43

.. todo::

    - Add literature references to this docstring.
    - Can we unify both classes in a single one? Mode of operation
      would be configured with a keyword (e.g. `identical=True`).
"""


class Theseus(CommandLineWrapper):

    """
    Superpose structures with different sequences but similar structures

    Parameters
    ----------
    max_iterations : int
        number of iterations for muscle

    Examples
    --------

    .. todo::

        Move these two examples to ``docs/examples`` or ``docs/tutorials``

    * Multiple structures of the cytochrome c protein from different species
    * Multiple mutated structures of hen egg white lysozyme.
    """

    def __init__(self, max_iterations: int = 32):
        self.max_iterations = max_iterations

        self.fastafile = "theseus.fasta"
        self.filemap_file = "theseus.filemap"
        self.alignment_file = "theseus.aln"
        self.alignment_app = "muscle"

    def __create_pdb(self, structures):
        """
        Create files with atomium objects

        Parameter
        ---------
        structures : list
            list of atomium objects
        """
        self.fetched_pdbs = structures
        self.fetched_pdbs_filename = []

        for pdbs in self.fetched_pdbs:
            pdb_filename = f"{pdbs.code}.pdb"
            pdbs.model.save(pdb_filename)
            self.fetched_pdbs_filename.append(pdb_filename)
        return self.fetched_pdbs_filename

    def _get_fasta(self):
        """
        Use Theseus to create fasta files

        .. todo::
            We can probably generate this from atomium directly
        """
        return subprocess.check_output(["theseus", "-f", "-F", *self.pdbs_filename])

    def _concatenate_fasta(self):
        """
        Concatenate the fasta files created with Theseus into one multiple sequence fasta file
        """
        with open(self.fastafile, "w") as outfile:
            for fname in self.pdbs_filename:
                with open(f"{fname}.fst") as infile:
                    for line in infile:
                        outfile.write(line)

    def _filemap(self):
        """
        Create filemap for Theseus
        """
        with open(self.filemap_file, "w") as outfile:
            for fname in self.pdbs_filename:
                outfile.write(f"{fname} {fname}\n")

    def _calculate(self, structures, identical: bool = True, **kwargs):
        """
        Align the sequences with an alignment tool (``muscle``)

        .. todo::

            Can we use a different alignment tool, preferrably in Python? E.g. biotite?



        A mode for superpositioning macromolecules with
        identical sequences and numbers of residues,
        for instance, multiple models in an NMR family
        or multiple structures from different crystal
        forms of the same protein.


        Parameter
        ---------
        structures : list
            list of atomium objects

        **kwargs : dictionary
            optional parameter
        """

        with enter_temp_directory(remove=False) as (cwd, tmpdir):
            print("DEBUG: Running in", tmpdir, " -- TODO: DELETE BEFORE MERGE --")

            self.pdbs_filename = self.__create_pdb(structures)

            if identical:
                superposition_output = self._run_theseus()
            else:
                self._get_fasta()
                self._concatenate_fasta()
                self._filemap()
                seq_alignment_output = subprocess.check_output(
                    [
                        self.alignment_app,
                        "-maxiters",
                        str(self.max_iterations),
                        "-in",
                        self.fastafile,
                        "-out",
                        self.alignment_file,
                        "-clwstrict",
                    ],
                    universal_newlines=True,
                )
                self._parse_alignment(seq_alignment_output)
                print(seq_alignment_output)
                superposition_output = self._run_theseus_align()
                print(superposition_output)
                print("-- OUTPUT WE NEED TO PARSE BEFORE DELETING TEMPFILES --")
                print(*list(Path(tmpdir).glob("theseus_*")), sep="\n")
        return self._parse_superposition(superposition_output)

    def _parse_alignment(self, output):
        """
        Parse the output from the MSA program (muscle, by default)

        Parameters
        ----------
        output : bytes
        """
        return output

    def _parse_superposition(self, output):
        """
        Parse the output from theseus itself

        Parameters
        ----------
        output : bytes
        """
        for line in output.splitlines():
            if "Classical" in line:
                rmsd = line.split()[5]
        return {"rmsd": rmsd}

    def _run_theseus(self):
        """
        Superpose with Theseus
        """
        output = subprocess.check_output(
            ["theseus", *self.pdbs_filename], universal_newlines=True
        )
        return output

    def _run_theseus_align(self):
        """
        Superpose with Theseus based on the sequence alignment
        """
        output = subprocess.check_output(
            [
                "theseus",
                "-f",
                "-M",
                self.filemap_file,
                "-A",
                self.alignment_file,
                *self.pdbs_filename,
            ],
            universal_newlines=True,
        )
        return output


if __name__ == "__main__":
    import sys
    import atomium

    # pdb_ids = sys.argv[1:3]
    pdb_ids = ["6HG4", "6HG9"]

    models = [atomium.fetch(pdb_id) for pdb_id in pdb_ids]
    theseus = Theseus()

    # theseus.calculate((models))
    theseus._calculate(models, False)

