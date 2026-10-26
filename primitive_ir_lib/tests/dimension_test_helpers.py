from __future__ import annotations

import base64
import hashlib
from pathlib import Path

import cv2
import numpy as np

from primitive_ir_lib.dimension_observer import DimensionCluster, DimensionDisposition
from primitive_ir_lib.text_extraction import RawText



_FROZEN_DIMENSION_WITNESS_PNGS = {
    'complete': (
        'iVBORw0KGgoAAAANSUhEUgAAANwAAACWCAIAAAA6+3HcAAADpUlEQVR42u3dzytlbQDA8bnuiMUoP7rNQhZTFpJYzMLCKGnk'
        'R2JjJyzslBK7iT/BwkKT2IiSyMLGQhGKjSykCEVZiEiR/Fi47/O+t+TF5vUSU5/P4nTuuWf1+Hqec869dSPxePwTfCRJhgBR'
        'gigRJYgSUYIoESWIEkSJKEGUiBJEiShBlIgSRAmiRJQgSkQJokSUIEoQJaIEUSJKECWiBFEiShAliBJRwv/w2RA86/r6enBw'
        '8Nu3b7W1tU/fjcfjw8PDR0dHnZ2dycnJiYOHh4dTU1Obm5s5OTnV1dWFhYWG8YXiPLG3t/f9+/cwOPX19c+e8Pv378ToHR8f'
        'J46sra19/fo1Eon8+PEj8dbIyIiRfBnL92Ozs7OhyLu7u9zc3GdP2Nra6urqqqmpeXgwTJnRaHRjY2Npaam1tTUc6ejouLi4'
        'MJ6uKV9BaK6hoWF5eTkWiz199/b2trGxMRTZ3Nx8f/Dy8nJhYSEczM/PD+v+3NxcmEpPT09XVlaMpyhfQXt7+8DAQGpq6rPv'
        '9vT0hEvJcMLDg/v7+2HRKSsrC/sTExNVVVV1dXVhf3d313i60Xlb8/Pzvb29MzMzmZmZD49fXV2FbVpaWtj29/cPDQ19+fIl'
        '7N/c3Bg0M+UbOjs7a2lpCfNoRUXF40FM+nsYw2Xo6upqmGILCgoSPy4Y7nuMm5nyDfX19R0cHCwuLpaUlISXJycnYfvz58/w'
        '8tevX2F/Z2dnenq6ra0t7G9vb4dtVlaWcRPlGyovL384862vr4fyKisri4qKsrOzMzIyxsbGzs/PE5ebYYkP2zBlGreX8FTs'
        'kY2Njel/5OXlFRcXJ/bDvPjotNHR0U8PnlN2d3cnxjPchof99PT00tJSg/kyonysqanp6b/u+Pj4o9MmJyej0Wi40Ey8vL29'
        'vX9IlJKSEu6+73vlv4r4ve/XXXYODw9jsdj9Z4+8gCjxSAhEiShBlIgSRIkoQZQgSj66d/uWkO8a/hHe5QO/JEXy0f5Slm8s'
        '3x9gdeCDr2ZmStx9gygRJYgSUYIoESWIEkSJKEGUiBJEiShBlIgSRAmiRJQgSkQJokSUIEoQJaIEUSJKECWiBFEiShAliBJR'
        'gigRJYgSUYIoQZSIEkSJKEGUiBJEiShBlCBKRAmiRJQgSkQJogRRIsp/i8fj91s+pnf8G0WUgZkSRIkoQZSIEkSJKEGUIEpE'
        'CaJElCBKRAmiRJQgShAlogRRIkoQJaIEUYIoESWIkj/aXw4AIOMy6bjeAAAAAElFTkSuQmCC'
    ),
    'interrupted': (
        'iVBORw0KGgoAAAANSUhEUgAAANwAAACWCAIAAAA6+3HcAAADu0lEQVR42u3ZzyukfwDA8e+s1UoUu02KHJSDNpH24LC2NpEf'
        'iYubcHBTLo7iT3Bw0LZxEbXJ5uCiHIgDFzmICEU5TLaV2tKuOZj9fL9Tk/A92Pp+Z0av1+HpM888xXyet88zzyOSSCT+gkzy'
        'whQgShAlogRRIkoQJaIEUYIoESWIElGCKBEliBJRgihBlIgSRIkoQZSIEkQJokSUIEpECaJElCBKRAmiBFEiShAlogRRIkoQ'
        'JYgSUYIoESWIElGCKBEliBJEiShBlIgSRIkoIW1emoJ/8+vXr6mpqYqKio6OjofvJhKJmZmZi4uL4eHh3Nzc5M5YLLa4uHhw'
        'cFBeXt7W1lZTU2Ma/0SCx5yenr579y7MT1dX16MHfPr0KTmB3759S+7Z2dkpKSmJRCINDQ3Jt2ZnZ83kH0hblJn897mysvL6'
        '9eu6urrKyspHowxrYX5+fnt7+90oP378WFpaur+/H8YDAwPhrTdv3vz48eN5zMn/KT3fKcNykoEnIPVbHR4ednd3b25uRqPR'
        'h4fF4/Genp5QZF9fX2rn9fX1+vp62Pn27dtw3V9dXQ1L6eXl5dbW1vOYEzc6aVsVkoOhoaHPnz/n5eU9etjY2Fj4KhkOuLvz'
        '7OwsuViG8cLCQmtra2dnZxifnJw89afzMkM6yBZra2vj4+PLy8vh+n53/8+fP8O2sLAwbCcnJ6enpwsKCsL45uYmS2cjjSu3'
        'lfIJrq6u+vv7wzra3Nx8fx5f/D2Tt7e329vbYYmtrq5OFpaZF2Ur5fMxMTFxfn6+sbHx/v378PL79+9h29TUFF6OjIyE8fHx'
        '8dLS0uDgYBgfHR0l73XMmyj/Q42NjXdXvt3d3VBeS0tLbW1tWVlZcXHxly9fwu128utmuMSHbVgyzVt23PNn+FPSvb29pX9U'
        'VVXV19cnx2FdvHfY3Nzc3UdCo6OjyQ8VbsPDuKio6MOHD1n8sDB950iUj+jt7X341zs/P3/vsK9fv+bk5IQvmsmX8Xg89ZDo'
        '1atX4e471asonySSlju+1EXw+T0HCZ8oFotFo9HU/x6zVBrPkSjJuHPkkRAZR5SIEkSJKEGUiBJEiShBlCBKRAmiRJQgSkQJ'
        'okSUIEoQJaIEUSJKECWiBFGCKBEliBJRgigRJYgSUYIoQZSIEkSJKEGUiBJECaJElCBKRAmiRJQgSkQJooRMizKRSKS2ZKY0'
        'nqOIMrBSgigRJYgSUYIoESWIEkSJKEGUiBJEiShBlIgSRAmiRJQgSkQJokSUIEoQJaIEUZLVfgMmyUTB+dziyQAAAABJRU5E'
        'rkJggg=='
    ),
    'insufficient_association': (
        'iVBORw0KGgoAAAANSUhEUgAAANwAAACWCAIAAAA6+3HcAAADo0lEQVR42u3dzytlfRzA8bnuiAXF6GYhC2UhaWYxCwuURH6k'
        'sbETFnZqahq7iT/BwkLS2IiSyMLGQhGKjWahW4SiLG5EaqZpxl24z/d5bkmXzeOhoef1WpzOPfdsfLx9zzmXEkmlUq/gOcky'
        'AkQJokSUIEpECaJElCBKECWiBFEiShAlogRRIkoQJYgSUYIoESWIElGCKEGUiBJEiShBlIgSRIkoQZQgSkQJ/8FrI7jX79+/'
        'v379WlZW1t7efvfdVCo1OTl5enr6+fPn7Ozs9MFEIrGwsLC7u1taWtra2vr27VtjfKAUdxwdHb1//z4Mp6Oj494TxsbG0tM7'
        'OztLH/n27VtxcXEkEqmtrU2/NTU1ZZIP4/KdaXl5ORR5fX1dXl5+7wl7e3sDAwNtbW23D4YlMxqNxuPxjY2Nvr6+cOTTp08/'
        'fvwwT/eUjyA019nZubm5GYvF7r6bTCa7urpCkT09PTcHf/78uba2Fg5WVlaG6/7KykpYSi8uLra2tsxTlI/g48eP4+Pjubm5'
        '9747NDQUbiXDCbcPHh8fh4tOfX192J+bm2tpafnw4UPYPzw8NE8POk9rdXV1eHh4aWnpzZs3t4//+vUrbPPz88N2dHR0YmIi'
        'Ly8v7F9dXRmalfIJXV5e9vb2hnW0qakpc4hZf48x3IZub2+HJbaqqir9zwXDc4+5WSmf0MjIyMnJyfr6ek1NTXh5fn4eto2N'
        'jeHlly9fwv7BwcHi4mJ/f3/Y39/fD9uioiJzE+UTamhouL3y7ezshPKam5vfvXtXUlJSWFg4MzPz/fv39O1muMSHbVgyze0h'
        'fCqWIR6PL/6joqKiuro6vR/WxYzTpqenX936nHJwcDA9z/AYHvYLCgrq6uoM82FEmam7u/vuj+7s7GzGafPz89FoNNxopl8m'
        'k8mbD4lycnLC0/dNr/xbEf/v+3EvO4lEIhaL3fzukQcQJT4SAlEiShAlogRRIkoQJYiS5+6P/ZWQvzV8Ef7IL/yyFMlz+065'
        'fPPsVsrX/8OvGQ86IEpECaJElCBKRAmiBFEiShAlogRRIkoQJYgSUYIoESWIElGCKBEliBJEiShBlIgSRIkoQZQgSkQJokSU'
        'IEpECaJElCBKECWiBFEiShAlogRRgigRJYgSUYIoESWIElGCKEGUiBJeVJSpVOpmCxkiysBKCaJElCBKRAmiRJQgShAlogRR'
        'IkoQJaIEUSJKECWIElGCKBEliBJRgihBlIgSRMmL9hf0ZR3jH7YjRwAAAABJRU5ErkJggg=='
    ),
    'unrelated_collinear_fragment': (
        'iVBORw0KGgoAAAANSUhEUgAAANwAAACWCAIAAAA6+3HcAAADzUlEQVR42u3ZzyulawDA8WtmRBPFTCdFFspCEsliFkZJ5Edi'
        'YycsZqdsZin+BAsLTWKjURJZ2CgLYsFGFiJCURYiUkqDxZz73Hvq5OLerilzDn0+i7f3vOftOOd5v+d5z/tKiUajf0AyeWMI'
        'ECWIElGCKBEliBJRgihBlIgSRIkoQZSIEkSJKEGUIEpECaJElCBKRAmiBFEiShAlogRRIkoQJaIEUYIoESWIElGCKBEliBJE'
        'iShBlIgSRIkoQZSIEkQJokSUIEpECaJElJAw7wzBv7m+vh4ZGSkoKGhubn74bDQaHRsbOzk5+fr1a2pqamzj8fHxzMzM9vZ2'
        'fn5+Y2NjaWmpYfwVUR5zcHBQUVERxqe1tfXRHb59+xYbwNPT09iW9fX1nJyclJSUz58/x576/v27kfwFCYsymb+f8/PzHz58'
        'KC8vLywsfDTKMBe+f/++qanpbpTV1dW5ublbW1th/cuXL+Gpjx8/Xl5evo4x+Z2zYWJ+U4bpJAkPQPxd7ezstLW1raysRCKR'
        'h7vd3t62t7eHIjs7O+Mbr66ulpaWwsbi4uJw3l9YWAhT6fn5+erq6isYk+d4b//xmi50/vHdja309PQMDw+np6c/ult/f3/4'
        'KRl2uLvx8PAwNlmG9ampqYaGhpaWlrC+v7//1L+ezCPze17z3ev7tM9qcXFxYGBgbm4unN/vbv/x40dYZmZmhuXQ0NDo6GhG'
        'RkZYv7m5eaGjcW8m+53vzUz5BBcXF11dXWEerauruz+Ob/4ayZ8/f66trYUptqSkJHYUk/Ok7JbQ6zE4OHh0dLS8vFxZWRke'
        'np2dhWVtbW142NvbG9b39vZmZ2e7u7vD+u7ubuxax7iJ8hnV1NTcnfk2NjZCefX19WVlZXl5ednZ2RMTE+FyO/ZzM5ziwzJM'
        'mcbtZdynTPK7pJubm7N/Kyoq+vTpU2w9zIv3dhsfH797S6ivry/2ocJleFjPysqqqqp6wTcLE3eMRPmIjo6Oh9/eycnJe7tN'
        'T0+/ffs2/NCMPby9vY3fJEpLSwtX3/FeRfkkKQm54oufBF/c1ff/OfMcHx9HIpH4/x5fqAQeI1GSdMfILSGSjigRJYgSUYIo'
        'ESWIElGCKEGUiBJEiShBlIgSRIkoQZQgSkQJokSUIEpECaIEUSJKECWiBFEiShAlogRRgigRJYgSUYIoESWIEkSJKEGUiBJE'
        'iShBlIgSRAnJFmU0Go0vSU4JPEYpysBMCaJElCBKRAmiRJQgShAlogRRIkoQJaIEUSJKECWIElGCKBEliBJRgihBlIgSRMmL'
        '9ifm5f0ASdAAxQAAAABJRU5ErkJggg=='
    ),
    'competing_witness': (
        'iVBORw0KGgoAAAANSUhEUgAAANwAAACWCAIAAAA6+3HcAAADy0lEQVR42u3czyulawDA8XvGaCRTmE5qZKEsJolkYYGSTH4k'
        'NnbCwk7ZWIo/wcJCk9hMoySysFEWxIKNZjHNRCjK4mQaKaUZFs597n1Lwl2Yuvec434+i9Nz3vMWnvfrec/7yoklk8k/IJ28'
        'MAWIEkSJKEGUiBJEiShBlCBKRAmiRJQgSkQJokSUIEoQJaIEUSJKECWiBFGCKBEliBJRgigRJYgSUYIoQZSIEkSJKEGUiBJE'
        'CaJElCBKRAmiRJQgSkQJogRRIkoQJaIEUSJKSJmXpuCf/Pr1a3p6urS0tKOj4+GryWTy48ePp6enw8PD2dnZ0cZEIrG0tLS7'
        'u1tSUtLW1lZZWWkaf0eSxxwdHdXU1IT56erqenSHDx8+RBP4/fv3aMvnz5+LiopisVh9fX300qdPn8zkb0hZlOn8+7m6ulpY'
        'WFhdXV1WVvZolGEtzM3NbW9vvxtlY2Pj27dvv337FsYDAwPhpTdv3lxcXDyPOfkvpeY9ZVhO0vAA3H5Xe3t73d3dW1tb8Xj8'
        '4W7X19c9PT2hyL6+vtuNl5eXGxsbYWN5eXk476+trYWl9OzsbHt7+3nMiQudlK0K0WBoaGhqaionJ+fR3cbGxsJbybDD3Y3H'
        'x8fRYhnGCwsLra2tnZ2dYXx4ePjUr87LNOkgU6yvr4+Pj6+srITz+93tP3/+DI+vX78Oj5OTkzMzM3l5eWF8dXWVobORwpXb'
        'SvkE5+fn/f39YR19//79/Xl88ddM3tzc7OzshCW2oqIiKiw9T8pWyudjYmLi5ORkc3Ozrq4uPP3x40d4bG5uDk9HRkbC+ODg'
        'YHl5eXBwMIz39/ejax3zJsp/UVNT092V78uXL6G8lpaWqqqq4uLigoKCubm5cLkdvd0Mp/jwGJZM85YZ1/xpfpf069evy397'
        '9+5dbW1tNA7r4r3dZmdn794SGh0djX6ocBkexvn5+Q0NDRl8szB1x0iUj+jt7X342zs/P39vt8XFxaysrPBGM3p6fX19e5Po'
        '1atX4er7tldRPkksJVd8tyfB53cfJPxEiUQiHo/f/u0xQ6XwGImStDtGbgmRdkSJKEGUiBJEiShBlIgSRAmiRJQgSkQJokSU'
        'IEpECaIEUSJKECWiBFHyP5PiD7jySXlYKRElZNzp22cJpS0fLw2iRJQgSkQJokSUIEpECaIEUSJKECWiBFEiShAliBJRgigR'
        'JYgSUcLzjjL6d2//9J3OUniMYsrASgmiRJQgSkQJokSUIEoQJaIEUSJKECWiBFEiShAliBJRgigRJYgSUYIoQZSIEkRJRvsT'
        'KFVHyMzwnKoAAAAASUVORK5CYII='
    ),
}

_FROZEN_DIMENSION_WITNESS_SHA256 = {'complete': 'eda2ba3bd8db1e8121e1bc6050be9f09a754b43318ae6a4ec356ad42ca96f20c', 'interrupted': 'b27bd0533494e3a46de66594b7054c60dc0b7d31bb6be1c5c9aa11e7e44d2323', 'insufficient_association': 'd89a74d4b21df04b1c42bc0bea0e7d3bdb536963de4fc3040c41cdfe5508b1cd', 'unrelated_collinear_fragment': 'fc7f4733503d2fbdad4fbe66fdb62d3f92e57cb295bd8203daa9703c17b1ddd4', 'competing_witness': 'ddb40b330034d2509000a5cc2f07533d1981cdc2b74fde0ab15d11e98c1a2f0a'}


_PR503_FROZEN_TRACK_PNGS = {
    'one_track_both_endpoints': (
        'iVBORw0KGgoAAAANSUhEUgAAANwAAACMCAIAAACYtlAhAAAC9ElEQVR4Ae3BwalcURDFwKP8g5bhwY+gDXMXqkJd8hLUJS9BXfIS'
        '1CUvQV3yEtQlL0Fd8hLUJS9BXfIS1CUvQV3yEtQlL0Fd8hLUJS9BXfIS1CUvQV3yEtQlL0Fd8hLUJS9BXfIS1CUvQV3yEtQlL0Fd'
        '8hLUJS9BXfIS1CUvQV3yEtQlL0Fd8hLUJS9BXfIS1CUvQV3yEtQlL0Fd8hLUJS9BXfIS1CUvQV3yEtQlL0Fd8hLUJS9BXfIS1CUv'
        'QV3yEtQlL0Fd8hLUJS9BXfIS1CUvQV3yEtQlL0Fd8hLUJS9BXfIS1CUvQV3yEtQlL0Fd8hLUJS9BXfIS1CUvQV3yEtQlL0Fd8hLU'
        'JS9BXfIS1OUPsB9Rlw/q8gH2U+qyoS5/gP2IunxQlzNgH3W5QV3OgH3U5QZ1OQP2UZcb1OUM2EddblCXM2AfdblBXc6AfdTlBnU5'
        'A/ZRlxvU5QzYR11uUJczYB91uUFdzoB91OUGdTkD9lGXG9TlDNhHXW5QlzNgH3W5QV3OgH3U5QZ1OQP2UZcb1OUM2EddblCXM2Af'
        'dblBXc6AfdTlBnU5A/ZRlxvU5QzYR11uUJczYB91uUFdzoB91OUGdTkD9lGXG9TlDNhHXW5QlzNgH3W5QV3OgH3U5QZ1OQP2UZcb'
        '1OUM2EddblCXM2AfdblBXc6AfdTlBnU5A/ZRlxvU5QzYR11uUJczYB91uUFdzoB91OUGdTkD9lGXG9TlDNhHXW5QlzNgH3W5QV3O'
        'gH3U5QZ1OQP2UZcb1OUM2EddblCXM2AfdblBXc6AfdTlBnU5A/ZRlxvU5QzYR11uUJczYB91uUFdzoB91OUGdTkD9lGXG9TlDNhH'
        'XW5QlzNgH3W5QV3OgH3U5QZ1OQP2UZcb1OUM2EddblCXM2AfdblBXc6AfdTlBnU5A/ZRlxvU5QzYR11uUJczYB91uUFdzoB91OUG'
        'dTkD9lGXG9TlfwDU5Qx1yUtQl7wEdclLUJe8BHXJS1CXvAR1yUtQl7zkH4NYYAfwYrbxAAAAAElFTkSuQmCC'
    ),
    'disconnected_inner_tracks': (
        'iVBORw0KGgoAAAANSUhEUgAAANwAAACMCAIAAACYtlAhAAADi0lEQVR4Ae3BMW7AMADEMOn/j1YBA52TdKmHI62YuYkVMzexYuYm'
        'VszcxIqZm1gxcxMrZm5ixcxNrJi5iRUzN7Fi5iZWzNzEipmbWDFzEytmbmLFzE2smLmJFTM3sWLmJlbM3MSKmZtYMXMTK2ZuYsXM'
        'TayYuYkVMzexYuYmVszcxIqZm1gxcxMrZm5ixcxNrJi5iRUzN7Fi5iZWzNzEipmbWDFzEytmbmLFzE2smLmJFTM3sWLmJlbM3MSK'
        'mZtYMXMTK2ZuYsXMTayYuYkVMzexYuYmVszcxIqZm1gxcxMrZm5ixcxNrJi5iRUzN7Fi5iZWzNzEipmbWDFzEytmbmLFzE2smLmJ'
        'FTM3sWLmJlbM3MSKmZtYMb9U/knFHFbMofKvKgasmF8q/6RiDivmBZWj4iOVo2KeWDEvqBwVH6kcFfPEinlB5aj4SOWomCdWzAsq'
        'R8VHKkfFPLFiXlA5Kj5SOSrmiRXzgspR8ZHKUTFPrJgXVI6Kj1SOinlixbygclR8pHJUzBMr5gWVo+IjlaNinlgxL6gcFR+pHBXz'
        'xIp5QeWo+EjlqJgnVswLKkfFRypHxTyxYl5QOSo+Ujkq5okV84LKUfGRylExT6yYF1SOio9Ujop5YsW8oHJUfKRyVMwTK+YFlaPi'
        'I5WjYp5YMS+oHBUfqRwV88SKeUHlqPhI5aiYJ1bMCypHxUcqR8U8sWJeUDkqPlI5KuaJFfOOWvEnasW8YMXMTayYuYkVMzexYuYm'
        'VszcxIqZm1gxcxMrZm5ixcxNrJi5iRUzN7Fi5iZWzNzEinlHrfgTtWJesGJeUDkqPlI5KuaJFfOCylHxkcpRMU+smBdUjoqPVI6K'
        'eWLFvKByVHykclTMEyvmBZWj4iOVo2KeWDEvqBwVH6kcFfPEinlB5aj4SOWomCdWzAsqR8VHKkfFPLFiXlA5Kj5SOSrmiRXzgspR'
        '8ZHKUTFPrJgXVI6Kj1SOinlixbygclR8pHJUzBMr5gWVo+IjlaNinlgxL6gcFR+pHBXzxIp5QeWo+EjlqJgnVswLKkfFRypHxTyx'
        'Yl5QOSo+Ujkq5okV84LKUfGRylExT6yYF1SOio9Ujop5YsW8oHJUfKRyVMwTK+YFlaPiI5WjYp5YMS+oHBUfqRwV88SKeUHlqPhI'
        '5aiYJ1bMO2rFn6gV84IVMzexYuYmVszcxIqZm1gxcxMrZm5ixcxNrJi5yQ/KO8YHadV1CwAAAABJRU5ErkJggg=='
    ),
    'distinct_outer_tracks': (
        'iVBORw0KGgoAAAANSUhEUgAAANwAAACMCAIAAACYtlAhAAADn0lEQVR4Ae3BwW0EQRDEMCn/oGWgAaewN48irZh5iRUzL7Fi5iVW'
        'zLzEipmXWDHzEitmXmLFzEusmHmJFTMvsWLmJVbMvMSKmZdYMfMSK2ZeYsXMS6yYeYkVMy+xYuYlVsy8xIqZl1gx8xIrZl5ixcxL'
        'rJh5iRUzL7Fi5iVWzLzEipmXWDHzEitmXmLFzEusmHmJFTMvsWLmJVbMvMSKmZdYMfMSK2ZeYsXMS6yYeYkVMy+xYuYlVsy8xIqZ'
        'l1gx8xIrZl5ixcxLrJh5iRUzL7Fi5iVWzLzEipmXWDHzEitmXmLFzEusmHmJFTMvsWLmJVbMvMSKmZdYMfMSK2ZeYsXMS6yYeYkV'
        'My+xYuYlVsy8xIqZl1gx/1R+pGKOFXNUfqpiwIo5Kj9VMWDFHJVT8SGVUzFgxRyVU/EhlVMxYMUclVPxIZVTMWDFHJVT8SGVUzFg'
        'xRyVU/EhlVMxYMUclVPxIZVTMWDFHJVT8SGVUzFgxRyVU/EhlVMxYMUclVPxIZVTMWDFHJVT8SGVUzFgxRyVU/EhlVMxYMUclVPx'
        'IZVTMWDFHJVT8SGVUzFgxRyVU/EhlVMxYMUclVPxIZVTMWDFHJVT8SGVUzFgxRyVU/EhlVMxYMUclVPxIZVTMWDFHJVT8SGVUzFg'
        'xRyVU/EhlVMxYMUclVPxIZVTMWDFHJVT8SGVUzFgxRyVU/EhlVMxYMUclVPxIZVTMWDFHJVT8SGVUzFgxRyVU/EhlVMxYMUclVPx'
        'IZVTMWDFHJVT8SGVUzFgxRyVU/EhlVMxYMUclVPxIZVTMWDFHJVT8SGVUzFgxRyVU/EhlVMxYMUclVPxIZVTMWDFHJVT8SGVUzFg'
        'xRyVU/EhlVMxYMUclVPxIZVTMWDFHJVT8SGVUzFgxRyVU/EhlVMxYMUclVPxIZVTMWDFHJVT8SGVUzFgxRyVU/EhlVMxYMUclVPx'
        'IZVTMWDFHJVT8SGVUzFgxRyVU/EhlVMxYMUclVPxIZVTMWDFHJVT8SGVUzFgxRyVU/EhlVMxYMUclVPxIZVTMWDFHJVT8SGVUzFg'
        'xRyVU/EhlVMxYMUclVPxIZVTMWDFHJVT8SGVUzFgxRyVU/EhlVMxYMUclVPxIZVTMWDFHJVT8SGVUzFgxRyVU/EhlVMxYMUclVPx'
        'IZVTMWDFHJVT8SGVUzFgxRyVU/EhlVMxYMX8Uys+p1bMsWLmJVbMvMSKmZdYMfMSK2ZeYsXMS6yYeYkVMy/5A2ZwFBbC8bdJAAAA'
        'AElFTkSuQmCC'
    ),
}

_PR503_FROZEN_TRACK_SHA256 = {'one_track_both_endpoints': '2e4a09e2efcce60474b42320ee5455dedbb3e9562d8d3fd557bc3ab7c012d351', 'disconnected_inner_tracks': '5690af8f93c152d1b974401eeb257bd8be8392e98e0b246de43aa96373876143', 'distinct_outer_tracks': 'd9d8d4d3230a5fd9a5e9b03cdc34b39bfb45f3f50954401467780c59f7e180bc'}

def pr503_frozen_track_png(case: str) -> bytes:
    data = base64.b64decode(_PR503_FROZEN_TRACK_PNGS[case])
    if hashlib.sha256(data).hexdigest() != _PR503_FROZEN_TRACK_SHA256[case]:
        raise AssertionError(f"frozen PR503 track raster hash mismatch: {case}")
    return data


def pr503_frozen_track_image(case: str) -> np.ndarray:
    image = cv2.imdecode(np.frombuffer(pr503_frozen_track_png(case), dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise AssertionError(f"frozen PR503 track raster could not be decoded: {case}")
    return image

def frozen_dimension_witness_png(case: str) -> bytes:
    data = base64.b64decode(_FROZEN_DIMENSION_WITNESS_PNGS[case])
    if hashlib.sha256(data).hexdigest() != _FROZEN_DIMENSION_WITNESS_SHA256[case]:
        raise AssertionError(f"frozen dimension witness raster hash mismatch: {case}")
    return data


def frozen_dimension_witness_image(case: str) -> np.ndarray:
    data = frozen_dimension_witness_png(case)
    image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise AssertionError(f"frozen dimension witness raster could not be decoded: {case}")
    return image

def synthetic_horizontal_dimension() -> np.ndarray:
    image = np.full((140, 420, 3), 255, dtype=np.uint8)
    cv2.line(image, (80, 35), (340, 35), (0, 0, 0), 2)
    cv2.line(image, (80, 35), (80, 115), (0, 0, 0), 2)
    cv2.line(image, (340, 35), (340, 115), (0, 0, 0), 2)
    cv2.fillConvexPoly(image, np.array([[80, 35], [94, 29], [94, 41]], dtype=np.int32), (0, 0, 0))
    cv2.fillConvexPoly(image, np.array([[340, 35], [326, 29], [326, 41]], dtype=np.int32), (0, 0, 0))
    cv2.putText(image, "4500", (170, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
    return image


def synthetic_isolated_number_crop() -> np.ndarray:
    image = np.full((80, 180, 3), 255, dtype=np.uint8)
    cv2.putText(image, "4500", (25, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 2)
    return image


def synthetic_leader_annotation() -> np.ndarray:
    image = np.full((180, 300, 3), 255, dtype=np.uint8)
    cv2.line(image, (42, 125), (155, 50), (0, 0, 0), 2)
    cv2.fillConvexPoly(
        image,
        np.array([[42, 125], [58, 114], [58, 136]], dtype=np.int32),
        (0, 0, 0),
    )
    cv2.putText(image, "4500", (165, 58), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
    return image


def synthetic_unreadable_leader_geometry() -> np.ndarray:
    image = np.full((180, 300, 3), 255, dtype=np.uint8)
    cv2.line(image, (42, 125), (155, 50), (0, 0, 0), 2)
    cv2.fillConvexPoly(
        image,
        np.array([[42, 125], [58, 114], [58, 136]], dtype=np.int32),
        (0, 0, 0),
    )
    return image


def synthetic_diagonal_non_leader() -> np.ndarray:
    image = np.full((180, 300, 3), 255, dtype=np.uint8)
    cv2.line(image, (42, 125), (155, 50), (0, 0, 0), 2)
    return image


def synthetic_page_with_two_unreadable_dimensions_and_note() -> np.ndarray:
    page = np.full((360, 760, 3), 255, dtype=np.uint8)
    cv2.putText(page, "TITLE NOTE", (20, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 0), 2)
    for x0, x1 in ((60, 300), (440, 680)):
        y = 130
        cv2.line(page, (x0, y), (x1, y), (0, 0, 0), 2)
        cv2.line(page, (x0, y), (x0, 285), (0, 0, 0), 2)
        cv2.line(page, (x1, y), (x1, 285), (0, 0, 0), 2)
        cv2.fillConvexPoly(
            page,
            np.array([[x0, y], [x0 + 16, y - 7], [x0 + 16, y + 7]], dtype=np.int32),
            (0, 0, 0),
        )
        cv2.fillConvexPoly(
            page,
            np.array([[x1, y], [x1 - 16, y - 7], [x1 - 16, y + 7]], dtype=np.int32),
            (0, 0, 0),
        )
    return page


def synthetic_page_with_two_dimension_clusters_and_one_note() -> np.ndarray:
    page = np.full((420, 900, 3), 255, dtype=np.uint8)
    first = synthetic_horizontal_dimension()
    second = synthetic_horizontal_dimension()
    page[20:160, 20:440] = first
    page[190:330, 450:870] = second
    cv2.putText(page, "GHI CHU KY THUAT", (40, 390), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
    return page


def horizontal_dimension_cluster() -> DimensionCluster:
    return DimensionCluster(
        cluster_id="DIMCLUSTER-001",
        bbox_px=(0, 0, 420, 140),
        member_boxes=((160, 5, 260, 35),),
    )


def matching_horizontal_anchors() -> list[dict[str, object]]:
    return [
        {
            "type": "DATUM",
            "id": "FRONT_AXLE_CENTER",
            "view_id": "SIDE",
            "point_px": [80.0, 115.0],
            "confidence": 1.0,
        },
        {
            "type": "DATUM",
            "id": "REAR_AXLE_CENTER",
            "view_id": "SIDE",
            "point_px": [340.0, 115.0],
            "confidence": 1.0,
        },
    ]


def fake_ocr_4500(image_bgr: np.ndarray) -> list[RawText]:
    del image_bgr
    return [RawText(
        id="rawtext-4500",
        content="4500",
        bbox_px=(20, 15, 100, 55),
        rotation_deg=0.0,
        confidence=0.99,
        source="text_tesseract",
        parsed_value=4500.0,
        semantic_role="dimension_value",
    )]


def fake_ocr_unreadable(image_bgr: np.ndarray) -> list[RawText]:
    del image_bgr
    return [RawText(
        id="rawtext-unreadable",
        content="",
        bbox_px=(20, 15, 100, 55),
        rotation_deg=0.0,
        confidence=0.0,
        source="text_tesseract",
        parsed_value=None,
        semantic_role="unknown",
    )]


def fake_ocr_unreadable_leader(image_bgr: np.ndarray) -> list[RawText]:
    del image_bgr
    return [RawText(
        id="rawtext-unreadable-leader",
        content="8O?O",
        bbox_px=(165, 35, 250, 70),
        rotation_deg=0.0,
        confidence=0.20,
        source="text_tesseract",
        parsed_value=None,
        semantic_role="unknown",
    )]


def not_a_dimension_disposition(cluster_id: str) -> DimensionDisposition:
    return DimensionDisposition(
        cluster_id=cluster_id,
        disposition="NOT_A_DIMENSION",
        observation=None,
        reasons=("text_not_dimension_like",),
    )


def write_synthetic_dimension_page(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(path), synthetic_horizontal_dimension()):
        raise OSError(f"Cannot write synthetic page: {path}")
    return path
