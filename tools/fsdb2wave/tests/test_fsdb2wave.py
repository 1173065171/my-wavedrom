from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(ROOT))
sys.path.insert(0, ROOT)

from fsdb2wave import cli                                   # noqa: E402
from fsdb2wave.convert import format_bits, pad_bits          # noqa: E402
from fsdb2wave.errors import Fsdb2WaveError                  # noqa: E402
from fsdb2wave.timeutil import fmt_time, parse_time          # noqa: E402

FIX = os.path.join(HERE, 'fixtures', 'handshake.vcd')
FIX_REORDERED = os.path.join(HERE, 'fixtures', 'handshake_reordered.vcd')


def run(*argv):
    with redirect_stdout(io.StringIO()):
        return cli.run(list(argv))


def waves(result):
    res = {}

    def walk(items):
        for it in items:
            if isinstance(it, list):
                walk(it[1:])
            else:
                res[it['name']] = it
    walk(result['signal'])
    return res


def error_of(*argv) -> Fsdb2WaveError:
    try:
        run(*argv)
    except Fsdb2WaveError as err:
        return err
    raise AssertionError('expected an error')


class TimeTest(unittest.TestCase):
    def test_parse_and_format(self):
        self.assertEqual(parse_time('1.5us', 1000), 1500000)
        self.assertEqual(parse_time('35ns', 1000), 35000)
        self.assertEqual(parse_time('42', 1000), 42)
        self.assertEqual(fmt_time(5000, 1000), '5ns')
        self.assertEqual(fmt_time(1500000, 1000), '1.5us')
        self.assertEqual(fmt_time(0, 1000), '0ps')
        with self.assertRaises(Fsdb2WaveError):
            parse_time('3 parsecs', 1000)


class ValueTest(unittest.TestCase):
    def test_pad(self):
        self.assertEqual(pad_bits('101', 6), '000101')
        self.assertEqual(pad_bits('x1', 4), 'xxx1')
        self.assertEqual(pad_bits('z', 3), 'zzz')

    def test_radix(self):
        self.assertEqual(format_bits('10100101', 'hex'), 'A5')
        self.assertEqual(format_bits('00001000', 'hex'), '8')
        self.assertEqual(format_bits('1x0x0000', 'hex'), 'x0')
        self.assertEqual(format_bits('zzzz0001', 'hex'), 'z1')
        self.assertEqual(format_bits('10100101', 'dec'), '165')
        self.assertEqual(format_bits('10100101', 'sdec'), '-91')
        self.assertEqual(format_bits('1x', 'dec'), 'x')
        self.assertEqual(format_bits('0101', 'bin'), '0101')


class ConvertTest(unittest.TestCase):
    def test_handshake(self):
        res = run(FIX, '-c', 'tb.dut.clk', '-s', 'tb.dut.*', '-n', '12', '--strip-prefix', 'tb.dut')
        w = waves(res)
        self.assertEqual(w['clk']['wave'], 'p...........')
        self.assertEqual(w['rst_n']['wave'], '0.1.........')
        self.assertEqual(w['valid']['wave'], '0..1..0.....')
        self.assertEqual(w['ready']['wave'], 'x.0.1.......')
        self.assertEqual(w['addr'], {'name': 'addr', 'wave': 'x..=.=x.....', 'data': ['8', 'C']})
        self.assertEqual(w['data']['data'], ['A5', 'x0'])
        self.assertEqual(w['bus_z']['wave'], 'z....=z.....')
        self.assertEqual(w['clk_div2'], {'name': 'clk_div2', 'wave': 'p.....', 'period': 2})
        self.assertEqual(w['gclk']['wave'], 'l...p...l...')
        self.assertEqual(w['glitchy']['wave'], '0...........')
        self.assertEqual(w['temp']['data'], ['20.5', '21.25'])
        self.assertEqual(w['u_fifo.count']['wave'], '=..=======..')
        self.assertNotIn('ev', w)
        kinds = [x['kind'] for x in res['meta']['warnings']]
        self.assertIn('signal-skipped', kinds)
        glitch = [x for x in res['meta']['warnings'] if x['kind'] == 'multi-transition']
        self.assertEqual(glitch, [{'kind': 'multi-transition', 'signal': 'tb.dut.glitchy', 'cycle': 7, 'transitions': 2}])
        self.assertEqual(res['head'], {'text': 'tb.dut  5ns – 125ns', 'tick': 0})
        self.assertEqual(res['meta']['clock']['period'], '10ns')
        self.assertEqual(res['meta']['window'], {'start': '5ns', 'end': '125ns', 'startCycle': 0, 'cycles': 12})

    def test_same_timestamp_order_does_not_matter(self):
        args = ('-c', 'tb.dut.clk', '-s', 'tb.dut.*', '-n', '12', '--start', '@2')
        self.assertEqual(run(FIX, *args)['signal'], run(FIX_REORDERED, *args)['signal'])

    def test_start_time_equals_start_cycle(self):
        a = run(FIX, '-c', 'tb.dut.clk', '-s', 'tb.dut.valid', '-n', '5', '--start', '@3')
        b = run(FIX, '-c', 'tb.dut.clk', '-s', 'tb.dut.valid', '-n', '5', '--start', '33ns')
        self.assertEqual(a['signal'], b['signal'])
        self.assertEqual(a['head']['tick'], 3)
        self.assertEqual(waves(a)['tb.dut.valid']['wave'], '1..0.')

    def test_divided_clock_phase(self):
        res = run(FIX, '-c', 'tb.dut.clk', '-s', 'tb.dut.clk_div2', '-n', '6', '--start', '@1')
        self.assertEqual(waves(res)['tb.dut.clk_div2'], {'name': 'tb.dut.clk_div2', 'wave': 'n..', 'period': 2})

    def test_negedge_reference(self):
        res = run(FIX, '-c', 'tb.dut.clk', '-s', 'tb.dut.valid', '-n', '4', '--edge', 'neg', '--start', '@2')
        self.assertEqual(waves(res)['tb.dut.clk']['wave'], 'n...')
        self.assertEqual(res['meta']['window']['start'], '30ns')

    def test_radix_and_color(self):
        res = run(FIX, '-c', 'tb.dut.clk', '-s', 'tb.dut.data', '-n', '8', '--radix', 'sdec', '--color', 'signal')
        w = waves(res)['tb.dut.data']
        self.assertEqual(w['data'], ['-91', 'x'])
        self.assertEqual(w['wave'], 'x..2.2..')

    def test_sample_pre_vs_mid(self):
        tmp = tempfile.mkdtemp()
        try:
            path = os.path.join(tmp, 'late.vcd')
            with open(path, 'w') as f:
                f.write('$timescale 1ns $end $scope module t $end $var wire 1 ! clk $end '
                        '$var wire 1 " late $end $upscope $end $enddefinitions $end\n'
                        '#0 0! 0" #10 1! #15 0! #17 1" #20 1! #25 0! #30 1! #35 0! #40 1!\n')
            mid = run(path, '-c', 't.clk', '-s', 't.late', '-n', '3')
            pre = run(path, '-c', 't.clk', '-s', 't.late', '-n', '3', '--sample', 'pre')
            self.assertEqual(waves(mid)['t.late']['wave'], '01.')
            self.assertEqual(waves(pre)['t.late']['wave'], '1..')
        finally:
            shutil.rmtree(tmp)

    def test_group_alias_and_hscale(self):
        tmp = tempfile.mkdtemp()
        try:
            alias = os.path.join(tmp, 'alias.json')
            with open(alias, 'w') as f:
                json.dump({'tb.dut.rst_n': 'reset'}, f)
            res = run(FIX, '-c', 'tb.dut.clk', '-s', 'tb.dut.rst_n', '-s', 'tb.dut.u_fifo.*', '-s', 'tb.dut.valid',
                      '-n', '10', '--group-by-scope', '--strip-prefix', 'tb', '--alias', alias)
            sig = res['signal']
            self.assertEqual(sig[0]['name'], 'dut.clk')
            self.assertEqual(sig[1]['name'], 'reset')
            self.assertEqual(sig[2][0], 'dut.u_fifo')
            self.assertEqual([e['name'] for e in sig[2][1:]], ['full', 'count'])
            self.assertEqual(sig[3], ['dut', {'name': 'valid', 'wave': '0..1..0...'}])

            wide = run(FIX, '-c', 'tb.dut.clk', '-s', 'tb.dut.addr', '-n', '8', '--radix', 'bin')
            self.assertGreaterEqual(wide['config']['hscale'], 2)
            self.assertIn('bus-truncated', [x['kind'] for x in wide['meta']['warnings']])
        finally:
            shutil.rmtree(tmp)


class LimitTest(unittest.TestCase):
    def test_cycles_limit(self):
        err = error_of(FIX, '-c', 'tb.dut.clk', '-s', 'tb.dut.valid', '-n', '20', '--max-cycles', '10')
        self.assertEqual(err.code, 2)
        res = run(FIX, '-c', 'tb.dut.clk', '-s', 'tb.dut.valid', '-n', '20', '--max-cycles', '10', '--truncate')
        self.assertEqual(len(waves(res)['tb.dut.valid']['wave']), 10)
        self.assertEqual(error_of(FIX, '-c', 'tb.dut.clk', '-s', 'tb.dut.valid', '-n', '5',
                                  '--max-cycles', '5000').code, 2)

    def test_signals_limit(self):
        err = error_of(FIX, '-c', 'tb.dut.clk', '-s', 'tb.dut.*', '-n', '4', '--max-signals', '3')
        self.assertEqual(err.code, 2)
        res = run(FIX, '-c', 'tb.dut.clk', '-s', 'tb.dut.*', '-n', '4', '--max-signals', '3', '--truncate')
        self.assertEqual(len(res['signal']), 4)        # clock + 3

    def test_end_of_dump(self):
        res = run(FIX, '-c', 'tb.dut.clk', '-s', 'tb.dut.valid', '-n', '5', '--start', '@37')
        kinds = [x['kind'] for x in res['meta']['warnings']]
        self.assertIn('last-edge-estimated', kinds)
        self.assertIn('window-truncated', kinds)
        self.assertEqual(res['meta']['window']['cycles'], 3)
        self.assertEqual(error_of(FIX, '-c', 'tb.dut.clk', '-s', 'tb.dut.valid', '-n', '5',
                                  '--start', '@45').code, 1)

    def test_not_found(self):
        err = error_of(FIX, '-c', 'tb.dut.clk', '-s', 'tb.dut.vaild', '-n', '4')
        self.assertEqual(err.code, 3)
        self.assertIn('tb.dut.valid', err.candidates)
        self.assertEqual(error_of(FIX, '-c', 'tb.dut.clock', '-s', 'tb.dut.valid', '-n', '4').code, 3)
        self.assertEqual(error_of(FIX, '-c', 'tb.dut.addr', '-s', 'tb.dut.valid', '-n', '4').code, 1)

    def test_backend_unavailable(self):
        tmp = tempfile.mkdtemp()
        old = os.environ.get('FSDB2VCD')
        os.environ['FSDB2VCD'] = 'fsdb2vcd-does-not-exist'
        try:
            path = os.path.join(tmp, 'sim.fsdb')
            open(path, 'wb').close()
            self.assertEqual(error_of(path, '-c', 'a', '-s', 'b', '-n', '1').code, 4)
        finally:
            shutil.rmtree(tmp)
            if old is None:
                del os.environ['FSDB2VCD']
            else:
                os.environ['FSDB2VCD'] = old


class CliTest(unittest.TestCase):
    def _cli(self, *argv):
        return subprocess.run([sys.executable, '-m', 'fsdb2wave'] + list(argv), cwd=ROOT,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)

    def test_error_json(self):
        proc = self._cli(FIX, '-c', 'tb.dut.clk', '-s', 'tb.dut.vaild', '-n', '4')
        self.assertEqual(proc.returncode, 3)
        err = json.loads(proc.stderr)
        self.assertEqual(err['code'], 3)
        self.assertIn('tb.dut.valid', err['candidates'])
        proc = self._cli(FIX, '-s', 'tb.dut.valid')            # missing --clock / --cycles
        self.assertEqual(proc.returncode, 1)
        self.assertIn('required', json.loads(proc.stderr)['message'])

    @unittest.skipUnless(shutil.which('node') and os.path.isdir(os.path.join(REPO, 'node_modules')),
                         'node / repo dependencies not available')
    def test_output_renders_with_wavedrom(self):
        proc = self._cli(FIX, '-c', 'tb.dut.clk', '-s', 'tb.dut.*', '-n', '16', '--group-by-scope',
                         '--color', 'value', '--strip-prefix', 'tb')
        self.assertEqual(proc.returncode, 0, proc.stderr)
        script = ("const lib=require(%s);const onml=require('onml');"
                  "const src=JSON.parse(require('fs').readFileSync(0,'utf8'));"
                  "const svg=onml.stringify(lib.renderAny(0,src,lib.waveSkin));"
                  "if(!svg.startsWith('<svg'))process.exit(1);console.log(svg.length);") % json.dumps(os.path.join(REPO, 'lib'))
        node = subprocess.run(['node', '-e', script], input=proc.stdout, cwd=REPO,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        self.assertEqual(node.returncode, 0, node.stderr)
        self.assertGreater(int(node.stdout), 1000)


if __name__ == '__main__':
    unittest.main()
