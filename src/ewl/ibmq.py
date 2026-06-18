from functools import cached_property
from typing import Dict, Optional

from functools import cached_property
from typing import Dict, Optional

from qiskit import QuantumCircuit
from qiskit.compiler import transpile
from qiskit.circuit.library import UnitaryGate
from qiskit.quantum_info import Operator
from qiskit_aer import AerSimulator                        
from qiskit_aer.noise import NoiseModel 
from qiskit.quantum_info import Statevector

from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2 as Sampler
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager

from ewl import EWL
from ewl.utils import sympy_to_numpy_matrix


class EWL_IBMQ:
    def __init__(self, ewl: EWL, *, noise_model: Optional[NoiseModel] = None, instance: Optional[str] = None):
        if ewl.params:
            raise Exception('Please provide values for the following parameters: ' + ', '.join(map(str, ewl.params)))

        self.ewl = ewl
        self.noise_model = noise_model
        self._instance = instance  # np. "ibm-q/open/us-east/open-instance"

    @cached_property
    def service(self) -> QiskitRuntimeService:
        try:
            if self._instance:
                return QiskitRuntimeService(instance=self._instance)
            return QiskitRuntimeService()
        except Exception:
            raise RuntimeError('Please set IBM token with QiskitRuntimeService.save_account() '
                              'or pass instance="ibm-q/open/us-east/open-instance"')

    def _make_qc(self, *, measure: bool) -> QuantumCircuit:
        J = UnitaryGate(Operator(sympy_to_numpy_matrix(self.ewl.J)), label='$J$')
        J_H = UnitaryGate(Operator(sympy_to_numpy_matrix(self.ewl.J_H)), label='$J^\\dagger$')

        all_qbits = range(self.ewl.number_of_players)

        qc = QuantumCircuit(self.ewl.number_of_players)
        qc.append(J, all_qbits)
        qc.barrier()

        for i, player in enumerate(self.ewl.players):
            U_i = UnitaryGate(Operator(sympy_to_numpy_matrix(player)), label=f'$U_{{{i}}}$')
            qc.append(U_i, [i])

        qc.barrier()
        qc.append(J_H, all_qbits)

        if measure:
            qc.measure_all()

        return qc

    @cached_property
    def qc(self) -> QuantumCircuit:
        return self._make_qc(measure=True)

    def draw(self, **kwargs):
        return self.qc.draw('mpl', **kwargs)

    def draw_transpiled(self, backend_name: str, *, optimization_level: int = 3, **kwargs):
        backend = self.service.backend(backend_name)
        pm = generate_preset_pass_manager(backend=backend, optimization_level=optimization_level)
        transpiled_qc = pm.run(self.qc)
        return transpiled_qc.draw('mpl', **kwargs)

    def simulate_probs(self, backend_name: str = 'statevector', shots: int = 1024) -> Dict[str, float]:
        circ = self._make_qc(measure=False)
        state = Statevector.from_instruction(circ)
        probs_dict = state.probabilities_dict()        
        
        return dict(probs_dict)
       

    def simulate_counts(self, shots: int = 1024) -> Dict[str, int]:
       # simulator = AerSimulator(noise_model=self.noise_model)
     #   circ = transpile(self.qc, simulator) if self.noise_model is not None else self.qc
       # job = simulator.run(circ, shots=shots)
       # circ = self._make_qc(measure=False)
        circ = self._make_qc(measure=False)
        state = Statevector.from_instruction(circ)
        statistics = state.sample_counts(shots)
        return statistics

    def run(self, backend_name: str = 'least_busy', shots: int = 1024, *, optimization_level: int = 3, tries:int =1) -> Dict[str, int]:
        if backend_name == 'least_busy':
            if backend_name == 'least_busy':
                backend = self.service.least_busy(
                simulator=False,
                operational=True
                )
        else:
            backend = self.service.backend(backend_name)
        all_counts=[]
        sampler = Sampler(mode=backend)
        pm = generate_preset_pass_manager(backend=backend, optimization_level=optimization_level)
        isa_circuit = pm.run(self.qc)
        job = sampler.run([(isa_circuit)]*tries, shots=shots)
        result = job.result()

        for i in range(tries):
             counts = result[i].data.meas.get_counts()
             all_counts.append(counts)
        #pub_result = result[0]
        #ibmcounts = pub_result.data.meas.get_counts()
        #return ibmcounts
        return all_counts
