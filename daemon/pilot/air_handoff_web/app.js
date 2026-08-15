var Un = Object.defineProperty;
var Cn = (t, e, n) => e in t ? Un(t, e, { enumerable: !0, configurable: !0, writable: !0, value: n }) : t[e] = n;
var g = (t, e, n) => Cn(t, typeof e != "symbol" ? e + "" : e, n);
/*! noble-ciphers - MIT License (c) 2023 Paul Miller (paulmillr.com) */
function ne(t) {
  return t instanceof Uint8Array || ArrayBuffer.isView(t) && t.constructor.name === "Uint8Array" && "BYTES_PER_ELEMENT" in t && t.BYTES_PER_ELEMENT === 1;
}
const oe = (t) => t ? `"${t}" ` : "";
function Nt(t, e = "") {
  if (typeof t != "number")
    throw new TypeError(oe(e) + "expected number, got " + typeof t);
  if (!Number.isSafeInteger(t) || t < 0)
    throw new RangeError(oe(e) + "expected integer >= 0, got " + t);
  return t;
}
function H(t, e, n = "") {
  if (ne(t) && (e === void 0 || t.length === e))
    return t;
  e !== void 0 && Nt(e, "length");
  const r = ne(t), o = e !== void 0 ? ` of length ${e}` : "", i = r ? `length=${t.length}` : `type=${typeof t}`, s = oe(n) + "expected Uint8Array" + o + ", got " + i;
  throw r ? new RangeError(s) : new TypeError(s);
}
function Se(t, e = !0) {
  if (t.destroyed)
    throw new Error("hash was destroyed");
  if (e && t.finished)
    throw new Error("digest() was already called");
}
function $n(t, e) {
  H(t, void 0, "output");
  const n = e.outputLen;
  if (!(t.length >= n))
    throw new RangeError('"output" expected length >= ' + n);
}
function Nn(t, e) {
  if ($n(t, e), !mt(t))
    throw new Error("invalid output, must be aligned");
}
function qn(t) {
  return new Uint8Array(t.buffer, t.byteOffset, t.byteLength);
}
function st(t) {
  return new Uint32Array(t.buffer, t.byteOffset, Math.floor(t.byteLength / 4));
}
function et(...t) {
  for (let e = 0; e < t.length; e++)
    t[e].fill(0);
}
function Zt(t) {
  return new DataView(t.buffer, t.byteOffset, t.byteLength);
}
const Pt = new Uint8Array(new Uint32Array([287454020]).buffer)[0] === 68;
function Qe(t) {
  return t << 24 & 4278190080 | t << 8 & 16711680 | t >>> 8 & 65280 | t >>> 24 & 255;
}
const I = Pt ? (t) => t : (t) => Qe(t) >>> 0;
function Hn(t) {
  for (let e = 0; e < t.length; e++)
    t[e] = Qe(t[e]);
  return t;
}
const ae = Pt ? (t) => t : Hn;
function Fn(t, e) {
  if (t = H(t), e = H(e), t.length !== e.length)
    return !1;
  let n = 0;
  for (let r = 0; r < t.length; r++)
    n |= t[r] ^ e[r];
  return n === 0;
}
function Dn(t, e, n) {
  const r = e, o = n || (() => []), i = (c, f) => r(f, ...o(c)).update(c).digest(), s = r(new Uint8Array(t), ...o(new Uint8Array(0)));
  return i.outputLen = s.outputLen, i.blockLen = s.blockLen, i.create = (c, ...f) => r(c, ...f), i;
}
const kn = /* @__NO_SIDE_EFFECTS__ */ (t, e) => {
  function n(r, ...o) {
    if (H(r, void 0, "key"), t.nonceLength !== void 0) {
      const d = o[0];
      H(d, t.varSizeNonce ? void 0 : t.nonceLength, "nonce");
    }
    const i = t.tagLength, s = t.nonceLength !== void 0 ? 1 : 0;
    if (!t.withAAD) {
      for (let d = s; d < o.length; d++)
        if (ne(o[d]))
          throw new Error("AAD not supported");
    }
    t.withAAD && o[s] !== void 0 && H(o[s], void 0, "AAD");
    const c = e(r, ...o), f = (d, l) => {
      if (l !== void 0) {
        if (d !== 2)
          throw new Error("cipher output not supported");
        H(l, void 0, "output");
      }
    };
    let a = !1;
    return {
      encrypt(d, l) {
        if (a)
          throw new Error("cannot encrypt() twice with same key + nonce");
        return a = !0, H(d, void 0, "data"), f(c.encrypt.length, l), c.encrypt(d, l);
      },
      decrypt(d, l) {
        if (H(d, void 0, "data"), i && d.length < i)
          throw new Error('"ciphertext" expected length >= tagLength=' + i);
        return f(c.decrypt.length, l), c.decrypt(d, l);
      }
    };
  }
  return Object.assign(n, t), n;
};
function Mn(t, e, n = !0) {
  if (e === void 0)
    return new Uint8Array(t);
  if (H(e, t, "output"), n && !mt(e))
    throw new Error("invalid output, must be aligned");
  return e;
}
function Zn(t, e, n) {
  Nt(t), Nt(e);
  const r = new Uint8Array(16), o = Zt(r);
  return o.setBigUint64(0, BigInt(e), n), o.setBigUint64(8, BigInt(t), n), r;
}
function mt(t) {
  return t.byteOffset % 4 === 0;
}
function Et(t) {
  return Uint8Array.from(H(t));
}
function Pn(t = 32) {
  Nt(t, "bytesLength");
  const e = typeof globalThis == "object" ? globalThis.crypto : null;
  if (typeof (e == null ? void 0 : e.getRandomValues) != "function")
    throw new Error("crypto.getRandomValues must be defined");
  if (t > 65536)
    throw new RangeError(`"bytesLength" expected <= 65536, got ${t}`);
  return e.getRandomValues(new Uint8Array(t));
}
const nt = 16, tn = /* @__PURE__ */ new Uint8Array(16), lt = /* @__PURE__ */ st(tn), jn = 225, Yn = (t, e, n, r) => {
  const o = r & 1;
  return {
    s3: n << 31 | r >>> 1,
    s2: e << 31 | n >>> 1,
    s1: t << 31 | e >>> 1,
    // NIST SP 800-38D §6.3 applies `V >> 1` and XORs R on carry. In this
    // 4x32-bit split, R = 0xe1 || 0^120 lives in the top byte of s0.
    s0: t >>> 1 ^ jn << 24 & -(o & 1)
    // reduce % poly
  };
}, _t = (t) => (t >>> 0 & 255) << 24 | (t >>> 8 & 255) << 16 | (t >>> 16 & 255) << 8 | t >>> 24 & 255 | 0, zn = (t) => t > 64 * 1024 ? 8 : t > 1024 ? 4 : 2;
class Xn {
  // We select bits per window adaptively based on expectedLength
  constructor(e, n) {
    g(this, "blockLen", nt);
    g(this, "outputLen", nt);
    g(this, "s0", 0);
    g(this, "s1", 0);
    g(this, "s2", 0);
    g(this, "s3", 0);
    g(this, "finished", !1);
    g(this, "destroyed", !1);
    g(this, "t");
    g(this, "W");
    g(this, "windowSize");
    H(e, 16, "key"), e = Et(e);
    const r = Zt(e);
    let o = r.getUint32(0, !1), i = r.getUint32(4, !1), s = r.getUint32(8, !1), c = r.getUint32(12, !1);
    const f = [];
    for (let w = 0; w < 128; w++)
      f.push({ s0: _t(o), s1: _t(i), s2: _t(s), s3: _t(c) }), { s0: o, s1: i, s2: s, s3: c } = Yn(o, i, s, c);
    const a = zn(n || 1024);
    if (![1, 2, 4, 8].includes(a))
      throw new Error("ghash: invalid window size, expected 2, 4 or 8");
    this.W = a;
    const d = 128 / a, l = this.windowSize = 2 ** a, h = [];
    for (let w = 0; w < d; w++)
      for (let b = 0; b < l; b++) {
        let x = 0, R = 0, y = 0, v = 0;
        for (let p = 0; p < a; p++) {
          if (!(b >>> a - p - 1 & 1))
            continue;
          const { s0: m, s1: T, s2: S, s3: L } = f[a * w + p];
          x ^= m, R ^= T, y ^= S, v ^= L;
        }
        h.push({ s0: x, s1: R, s2: y, s3: v });
      }
    this.t = h;
  }
  _updateBlock(e, n, r, o) {
    e ^= this.s0, n ^= this.s1, r ^= this.s2, o ^= this.s3;
    const { W: i, t: s, windowSize: c } = this;
    let f = 0, a = 0, u = 0, d = 0;
    const l = (1 << i) - 1;
    let h = 0;
    for (const w of [e, n, r, o])
      for (let b = 0; b < 4; b++) {
        const x = w >>> 8 * b & 255;
        for (let R = 8 / i - 1; R >= 0; R--) {
          const y = x >>> i * R & l, { s0: v, s1: p, s2: E, s3: m } = s[h * c + y];
          f ^= v, a ^= p, u ^= E, d ^= m, h += 1;
        }
      }
    this.s0 = f, this.s1 = a, this.s2 = u, this.s3 = d;
  }
  update(e) {
    Se(this), H(e), e = Et(e);
    const n = st(e), r = Math.floor(e.length / nt), o = e.length % nt;
    for (let i = 0; i < r; i++)
      this._updateBlock(I(n[i * 4 + 0]), I(n[i * 4 + 1]), I(n[i * 4 + 2]), I(n[i * 4 + 3]));
    return o && (tn.set(e.subarray(r * nt)), this._updateBlock(I(lt[0]), I(lt[1]), I(lt[2]), I(lt[3])), et(lt)), this;
  }
  destroy() {
    this.destroyed = !0;
    const { t: e } = this;
    for (const n of e)
      n.s0 = 0, n.s1 = 0, n.s2 = 0, n.s3 = 0;
  }
  digestInto(e) {
    Se(this), Nn(e, this), this.finished = !0;
    const { s0: n, s1: r, s2: o, s3: i } = this, s = st(e);
    s[0] = n, s[1] = r, s[2] = o, s[3] = i, Pt || ae(s.subarray(0, nt / 4));
  }
  digest() {
    const e = new Uint8Array(nt);
    return this.digestInto(e), this.destroy(), e;
  }
}
const Ie = /* @__PURE__ */ Dn(16, (t, e) => new Xn(t, e), (t) => [t.length]), re = 16, Wn = 4, At = /* @__PURE__ */ new Uint8Array(re), Kn = 283;
function Vn(t) {
  if (![16, 24, 32].includes(t.length))
    throw new Error('"aes key" expected Uint8Array of length 16/24/32, got length=' + t.length);
}
function ue(t) {
  return t << 1 ^ Kn & -(t >> 7);
}
function Le(t, e) {
  let n = 0;
  for (; e > 0; e >>= 1)
    n ^= t & -(e & 1), t = ue(t);
  return n;
}
const Gn = /* @__PURE__ */ (() => {
  const t = new Uint8Array(256);
  for (let n = 0, r = 1; n < 256; n++, r ^= ue(r))
    t[n] = r;
  const e = new Uint8Array(256);
  e[0] = 99;
  for (let n = 0; n < 255; n++) {
    let r = t[255 - n];
    r |= r << 8, e[t[n]] = (r ^ r >> 4 ^ r >> 5 ^ r >> 6 ^ r >> 7 ^ 99) & 255;
  }
  return et(t), e;
})(), Jn = (t) => t << 24 | t >>> 8, Jt = (t) => t << 8 | t >>> 24;
function Qn(t, e) {
  if (t.length !== 256)
    throw new Error("wrong sbox length");
  const n = new Uint32Array(256).map((a, u) => e(t[u])), r = n.map(Jt), o = r.map(Jt), i = o.map(Jt), s = new Uint32Array(256 * 256), c = new Uint32Array(256 * 256), f = new Uint16Array(256 * 256);
  for (let a = 0; a < 256; a++)
    for (let u = 0; u < 256; u++) {
      const d = a * 256 + u;
      s[d] = n[a] ^ r[u], c[d] = o[a] ^ i[u], f[d] = t[a] << 8 | t[u];
    }
  return { sbox: t, sbox2: f, T0: n, T1: r, T2: o, T3: i, T01: s, T23: c };
}
const en = /* @__PURE__ */ Qn(Gn, (t) => Le(t, 3) << 24 | t << 16 | t << 8 | Le(t, 2)), to = /* @__PURE__ */ (() => {
  const t = new Uint8Array(16);
  for (let e = 0, n = 1; e < 16; e++, n = ue(n))
    t[e] = n;
  return t;
})();
function eo(t) {
  H(t);
  const e = t.length;
  Vn(t);
  const { sbox2: n } = en, r = [];
  (!Pt || !mt(t)) && r.push(t = Et(t));
  const o = ae(st(t)), i = o.length, s = (f) => pt(n, f, f, f, f), c = new Uint32Array(e + 28);
  c.set(o);
  for (let f = i; f < c.length; f++) {
    let a = c[f - 1];
    f % i === 0 ? a = s(Jn(a)) ^ to[f / i - 1] : i > 6 && f % i === 4 && (a = s(a)), c[f] = c[f - i] ^ a;
  }
  return et(...r), c;
}
function Tt(t, e, n, r, o, i) {
  return t[n << 8 & 65280 | r >>> 8 & 255] ^ e[o >>> 8 & 65280 | i >>> 24 & 255];
}
function pt(t, e, n, r, o) {
  return t[e & 255 | n & 65280] | t[r >>> 16 & 255 | o >>> 16 & 65280] << 16;
}
function Ue(t, e, n, r, o) {
  const { sbox2: i, T01: s, T23: c } = en;
  let f = 0;
  e ^= t[f++], n ^= t[f++], r ^= t[f++], o ^= t[f++];
  const a = t.length / 4 - 2;
  for (let w = 0; w < a; w++) {
    const b = t[f++] ^ Tt(s, c, e, n, r, o), x = t[f++] ^ Tt(s, c, n, r, o, e), R = t[f++] ^ Tt(s, c, r, o, e, n), y = t[f++] ^ Tt(s, c, o, e, n, r);
    e = b, n = x, r = R, o = y;
  }
  const u = t[f++] ^ pt(i, e, n, r, o), d = t[f++] ^ pt(i, n, r, o, e), l = t[f++] ^ pt(i, r, o, e, n), h = t[f++] ^ pt(i, o, e, n, r);
  return { s0: u, s1: d, s2: l, s3: h };
}
function St(t, e, n, r, o) {
  H(n, re, "nonce"), H(r), o = Mn(r.length, o);
  const i = n, s = st(i), c = Zt(i), f = st(r), a = st(o), u = e ? 0 : 12, d = r.length;
  let l = c.getUint32(u, e);
  for (let w = 0; w + 4 <= f.length; w += 4) {
    const { s0: b, s1: x, s2: R, s3: y } = Ue(t, I(s[0]), I(s[1]), I(s[2]), I(s[3]));
    a[w + 0] = f[w + 0] ^ I(b), a[w + 1] = f[w + 1] ^ I(x), a[w + 2] = f[w + 2] ^ I(R), a[w + 3] = f[w + 3] ^ I(y), l = l + 1 >>> 0, c.setUint32(u, l, e);
  }
  const h = re * Math.floor(f.length / Wn);
  if (h < d) {
    const { s0: w, s1: b, s2: x, s3: R } = Ue(t, I(s[0]), I(s[1]), I(s[2]), I(s[3])), y = new Uint32Array([w, b, x, R]);
    ae(y);
    const v = qn(y);
    for (let p = h, E = 0; p < d; p++, E++)
      o[p] = r[p] ^ v[E];
    et(y);
  }
  return o;
}
function no(t, e, n, r, o) {
  const i = o ? o.length : 0, s = t.create(n, r.length + i);
  o && s.update(o);
  const c = Zn(8 * r.length, 8 * i, e);
  s.update(r), s.update(c);
  const f = s.digest();
  return et(c), f;
}
const de = /* @__PURE__ */ kn({ blockSize: 16, nonceLength: 12, tagLength: 16, withAAD: !0, varSizeNonce: !0 }, function(e, n, r) {
  if (n.length < 8)
    throw new Error("aes/gcm: invalid nonce length");
  const o = 16;
  function i(c, f, a) {
    const u = no(Ie, !1, c, a, r);
    for (let d = 0; d < f.length; d++)
      u[d] ^= f[d];
    return u;
  }
  function s() {
    const c = eo(e), f = At.slice(), a = At.slice();
    if (St(c, !1, a, a, f), n.length === 12)
      a.set(n);
    else {
      const d = At.slice();
      Zt(d).setBigUint64(8, BigInt(n.length * 8), !1);
      const h = Ie.create(f).update(n).update(d);
      h.digestInto(a), h.destroy();
    }
    const u = St(c, !1, a, At);
    return { xk: c, authKey: f, counter: a, tagMask: u };
  }
  return {
    encrypt(c) {
      const { xk: f, authKey: a, counter: u, tagMask: d } = s(), l = new Uint8Array(c.length + o), h = [f, a, u, d];
      mt(c) || h.push(c = Et(c)), St(f, !1, u, c, l.subarray(0, c.length));
      const w = i(a, d, l.subarray(0, l.length - o));
      return h.push(w), l.set(w, c.length), et(...h), l;
    },
    decrypt(c) {
      const { xk: f, authKey: a, counter: u, tagMask: d } = s(), l = [f, a, d, u];
      mt(c) || l.push(c = Et(c));
      const h = c.subarray(0, -o), w = c.subarray(-o), b = i(a, d, h);
      if (l.push(b), !Fn(b, w))
        throw et(...l), new Error("aes-gcm: invalid tag");
      const x = St(f, !1, u, h);
      return et(...l), x;
    }
  };
}), oo = (t) => t / 2 ** 32 | 0, ro = (t) => t >>> 0;
function io(t, e, n, r) {
  const o = oo(n), i = ro(n);
  t.setUint32(e, r ? i : o, r), t.setUint32(e + 4, r ? o : i, r);
}
function ie(t) {
  return t instanceof Uint8Array || ArrayBuffer.isView(t) && t.constructor.name === "Uint8Array" && "BYTES_PER_ELEMENT" in t && t.BYTES_PER_ELEMENT === 1;
}
const se = (t) => t ? `"${t}" ` : "";
function ft(t, e = "") {
  if (typeof t != "number")
    throw new TypeError(se(e) + "expected number, got " + typeof t);
  if (!Number.isSafeInteger(t) || t < 0)
    throw new RangeError(se(e) + "expected integer >= 0, got " + t);
  return t;
}
function J(t, e, n = "") {
  if (ie(t) && (e === void 0 || t.length === e))
    return t;
  e !== void 0 && ft(e, "length");
  const r = ie(t), o = e !== void 0 ? ` of length ${e}` : "", i = r ? `length=${t.length}` : `type=${typeof t}`, s = se(n) + "expected Uint8Array" + o + ", got " + i;
  throw r ? new RangeError(s) : new TypeError(s);
}
function le(t) {
  if (typeof t != "function" || typeof t.create != "function")
    throw new TypeError("expected hash wrapped by utils.createHasher");
  if (ft(t.outputLen), ft(t.blockLen), t.outputLen < 1 || t.blockLen < 1)
    throw new Error("hash blockLen / outputLen must be >= 1");
}
const Ce = (t, e) => {
  if (t === null || typeof t != "object" || Array.isArray(t))
    throw new TypeError((e === "object" ? "" : `"${e}" `) + "expected object, got type=" + typeof t);
};
function qt(t, e = !0) {
  if (t.destroyed)
    throw new Error("hash was destroyed");
  if (e && t.finished)
    throw new Error("digest() was already called");
}
function nn(t, e) {
  J(t, void 0, "output");
  const n = e.outputLen;
  if (!(t.length >= n))
    throw new RangeError('"output" expected length >= ' + n);
}
function rt(...t) {
  for (let e = 0; e < t.length; e++)
    t[e].fill(0);
}
function Qt(t) {
  return new DataView(t.buffer, t.byteOffset, t.byteLength);
}
function X(t, e) {
  return t << 32 - e | t >>> e;
}
const on = /* @ts-ignore */ typeof Uint8Array.from([]).toHex == "function" && typeof Uint8Array.fromHex == "function", so = /* @__PURE__ */ Array.from({ length: 256 }, (t, e) => e.toString(16).padStart(2, "0"));
function jt(t) {
  if (J(t), on)
    return t.toHex();
  let e = "";
  for (let n = 0; n < t.length; n++)
    e += so[t[n]];
  return e;
}
function $e(t) {
  return t >= 48 && t <= 57 ? t - 48 : t >= 65 && t <= 70 ? t - 55 : t >= 97 && t <= 102 ? t - 87 : void 0;
}
function rn(t) {
  if (typeof t != "string")
    throw new TypeError("hex string expected, got " + typeof t);
  if (on)
    try {
      return Uint8Array.fromHex(t);
    } catch (o) {
      throw o instanceof SyntaxError ? new RangeError(o.message) : o;
    }
  const e = t.length, n = e / 2;
  if (e % 2)
    throw new RangeError("hex string expected, got unpadded hex of length " + e);
  const r = new Uint8Array(n);
  for (let o = 0, i = 0; o < n; o++, i += 2) {
    const s = $e(t.charCodeAt(i)), c = $e(t.charCodeAt(i + 1));
    if (s === void 0 || c === void 0) {
      const f = t[i] + t[i + 1];
      throw new RangeError('hex string expected, got non-hex character "' + f + '" at index ' + i);
    }
    r[o] = s * 16 + c;
  }
  return r;
}
function Ne(...t) {
  let e = 0;
  for (let r = 0; r < t.length; r++) {
    const o = t[r];
    J(o), e += o.length;
  }
  const n = new Uint8Array(e);
  for (let r = 0, o = 0; r < t.length; r++) {
    const i = t[r];
    n.set(i, o), o += i.length;
  }
  return n;
}
function co(t, e, n = "opts") {
  return Ce(t, "defaults"), e !== void 0 && Ce(e, n), Object.assign(t, e);
}
function fo(t, e = {}) {
  if (typeof t != "function")
    throw new TypeError('"hashCons" expected function, got type=' + typeof t);
  e = co({}, e, "info");
  const n = (o, i) => t(i).update(o).digest(), r = t(void 0);
  return n.outputLen = r.outputLen, n.blockLen = r.blockLen, n.canXOF = r.canXOF, n.create = (o) => t(o), Object.assign(n, e), Object.freeze(n);
}
function ao(t = 32) {
  ft(t, "bytesLength");
  const e = typeof globalThis == "object" ? globalThis.crypto : null;
  if (typeof (e == null ? void 0 : e.getRandomValues) != "function")
    throw new Error("crypto.getRandomValues must be defined");
  if (t > 65536)
    throw new RangeError(`"bytesLength" expected <= 65536, got ${t}`);
  return e.getRandomValues(new Uint8Array(t));
}
const uo = (t) => ({
  // Current NIST hashAlgs suffixes used here fit in one DER subidentifier octet.
  // Larger suffix values would need base-128 OID encoding and a different length byte.
  oid: Uint8Array.from([6, 9, 96, 134, 72, 1, 101, 3, 4, 2, t])
});
function lo(t, e, n) {
  return t & e ^ ~t & n;
}
function ho(t, e, n) {
  return t & e ^ t & n ^ e & n;
}
class po {
  constructor(e, n, r, o) {
    g(this, "blockLen");
    g(this, "outputLen");
    g(this, "canXOF", !1);
    g(this, "padOffset");
    g(this, "isLE");
    // For partial updates less than block size
    g(this, "buffer");
    g(this, "view");
    g(this, "finished", !1);
    g(this, "length", 0);
    g(this, "pos", 0);
    g(this, "destroyed", !1);
    this.blockLen = e, this.outputLen = n, this.padOffset = r, this.isLE = o, this.buffer = new Uint8Array(e), this.view = Qt(this.buffer);
  }
  update(e) {
    qt(this), J(e);
    const { view: n, buffer: r, blockLen: o } = this, i = e.length;
    let s = !1;
    for (let c = 0; c < i; ) {
      const f = Math.min(o - this.pos, i - c);
      if (f === o) {
        const a = Qt(e);
        for (; o <= i - c; c += o)
          this.process(a, c);
        s = !0;
        continue;
      }
      r.set(c === 0 && f === i ? e : e.subarray(c, c + f), this.pos), this.pos += f, c += f, this.pos === o && (this.process(n, 0), this.pos = 0, s = !0);
    }
    return this.length += e.length, s && this.roundClean(), this;
  }
  digestInto(e) {
    qt(this), nn(e, this), this.finished = !0;
    const { buffer: n, view: r, blockLen: o, isLE: i } = this;
    let { pos: s } = this;
    n[s++] = 128, n.fill(0, s), this.padOffset > o - s && (this.process(r, 0), n.fill(0)), io(r, o - 8, this.length * 8, i), this.process(r, 0), this.roundClean();
    const c = e === n ? r : Qt(e), f = this.outputLen, a = f / 4, u = this.get();
    if (f % 4 || a > u.length)
      throw new Error("invalid outputLen");
    for (let d = 0; d < a; d++)
      c.setUint32(4 * d, u[d], i);
  }
  digest() {
    const { buffer: e, outputLen: n } = this;
    this.digestInto(e);
    const r = e.slice(0, n);
    return this.destroy(), r;
  }
  _cloneIntoMeta(e) {
    const { buffer: n, length: r, finished: o, destroyed: i, pos: s } = this;
    return e.destroyed = i, e.finished = o, e.length = r, e.pos = s, s && e.buffer.set(n), e;
  }
  clone() {
    return this._cloneInto();
  }
}
const go = /* @__PURE__ */ Uint32Array.from([
  1779033703,
  3144134277,
  1013904242,
  2773480762,
  1359893119,
  2600822924,
  528734635,
  1541459225
]), wo = /* @__PURE__ */ Uint32Array.from([
  1116352408,
  1899447441,
  3049323471,
  3921009573,
  961987163,
  1508970993,
  2453635748,
  2870763221,
  3624381080,
  310598401,
  607225278,
  1426881987,
  1925078388,
  2162078206,
  2614888103,
  3248222580,
  3835390401,
  4022224774,
  264347078,
  604807628,
  770255983,
  1249150122,
  1555081692,
  1996064986,
  2554220882,
  2821834349,
  2952996808,
  3210313671,
  3336571891,
  3584528711,
  113926993,
  338241895,
  666307205,
  773529912,
  1294757372,
  1396182291,
  1695183700,
  1986661051,
  2177026350,
  2456956037,
  2730485921,
  2820302411,
  3259730800,
  3345764771,
  3516065817,
  3600352804,
  4094571909,
  275423344,
  430227734,
  506948616,
  659060556,
  883997877,
  958139571,
  1322822218,
  1537002063,
  1747873779,
  1955562222,
  2024104815,
  2227730452,
  2361852424,
  2428436474,
  2756734187,
  3204031479,
  3329325298
]), Q = /* @__PURE__ */ new Uint32Array(64);
class yo extends po {
  constructor(n, r) {
    super(64, n, 8, !1);
    // We cannot use array here since array allows indexing by variable
    // which means optimizer/compiler cannot use registers.
    // Numeric initializers matter: starting the fields as `undefined` changes
    // V8's field representation and makes sha256 3x slower (measured).
    g(this, "A", 0);
    g(this, "B", 0);
    g(this, "C", 0);
    g(this, "D", 0);
    g(this, "E", 0);
    g(this, "F", 0);
    g(this, "G", 0);
    g(this, "H", 0);
    this.A = r[0] | 0, this.B = r[1] | 0, this.C = r[2] | 0, this.D = r[3] | 0, this.E = r[4] | 0, this.F = r[5] | 0, this.G = r[6] | 0, this.H = r[7] | 0;
  }
  get() {
    const { A: n, B: r, C: o, D: i, E: s, F: c, G: f, H: a } = this;
    return [n, r, o, i, s, c, f, a];
  }
  // prettier-ignore
  set(n, r, o, i, s, c, f, a) {
    this.A = n | 0, this.B = r | 0, this.C = o | 0, this.D = i | 0, this.E = s | 0, this.F = c | 0, this.G = f | 0, this.H = a | 0;
  }
  _cloneInto(n) {
    return (n || (n = new this.constructor())).set(...this.get()), this._cloneIntoMeta(n);
  }
  process(n, r) {
    for (let l = 0; l < 16; l++, r += 4)
      Q[l] = n.getUint32(r, !1);
    for (let l = 16; l < 64; l++) {
      const h = Q[l - 15], w = Q[l - 2], b = X(h, 7) ^ X(h, 18) ^ h >>> 3, x = X(w, 17) ^ X(w, 19) ^ w >>> 10;
      Q[l] = x + Q[l - 7] + b + Q[l - 16] | 0;
    }
    let { A: o, B: i, C: s, D: c, E: f, F: a, G: u, H: d } = this;
    for (let l = 0; l < 64; l++) {
      const h = X(f, 6) ^ X(f, 11) ^ X(f, 25), w = d + h + lo(f, a, u) + wo[l] + Q[l] | 0, x = (X(o, 2) ^ X(o, 13) ^ X(o, 22)) + ho(o, i, s) | 0;
      d = u, u = a, a = f, f = c + w | 0, c = s, s = i, i = o, o = w + x | 0;
    }
    o = o + this.A | 0, i = i + this.B | 0, s = s + this.C | 0, c = c + this.D | 0, f = f + this.E | 0, a = a + this.F | 0, u = u + this.G | 0, d = d + this.H | 0, this.set(o, i, s, c, f, a, u, d);
  }
  roundClean() {
    rt(Q);
  }
  destroy() {
    this.destroyed = !0, this.set(0, 0, 0, 0, 0, 0, 0, 0), rt(this.buffer);
  }
}
class bo extends yo {
  constructor() {
    super(32, go);
  }
}
const wt = /* @__PURE__ */ fo(
  () => new bo(),
  /* @__PURE__ */ uo(1)
);
/*! noble-curves - MIT License (c) 2022 Paul Miller (paulmillr.com) */
function sn(t, e, n = () => {
}) {
  if (!Array.isArray(t))
    throw new TypeError(`"${e}" expected array, got type=${typeof t}`);
  for (let r = 0; r < t.length; r++)
    n(t[r], `${e}[${r}]`);
  return t;
}
const at = (t, e, n) => J(t, e, n), cn = ft;
function ut(t, e = "object") {
  if (t === null || typeof t != "object" || Array.isArray(t))
    throw new TypeError(e === "object" ? "expected valid options object" : `"${e}" expected object, got type=${typeof t}`);
  return t;
}
function yt(t, e) {
  if (typeof t != "function")
    throw new TypeError(`"${e}" is invalid: expected function, got ${typeof t}`);
  return t;
}
const mo = jt, Eo = (t) => rn(t), fn = ie, an = (t) => ao(t), Ht = /* @__PURE__ */ BigInt(0), qe = /* @__PURE__ */ BigInt(1), xo = (t) => t ? `"${t}" ` : "";
function Yt(t, e = "") {
  if (typeof t != "boolean")
    throw new TypeError(xo(e) + "expected boolean, got type=" + typeof t);
  return t;
}
function Bo(t) {
  if (typeof t == "bigint") {
    if (!ct(t))
      throw new RangeError("positive bigint expected, got " + t);
  } else
    cn(t);
  return t;
}
function ce(t, e = "") {
  if (typeof t != "number") {
    const n = e && `"${e}" `;
    throw new TypeError(n + "expected number, got type=" + typeof t);
  }
  if (!Number.isSafeInteger(t)) {
    const n = e && `"${e}" `;
    throw new RangeError(n + "expected safe integer, got " + t);
  }
}
function un(t) {
  if (typeof t != "string")
    throw new TypeError("hex string expected, got " + typeof t);
  return t === "" ? Ht : BigInt("0x" + t);
}
function dn(t) {
  return un(jt(t));
}
function Ft(t) {
  return un(jt(xt(J(t)).reverse()));
}
function ln(t, e) {
  if (ft(e), e === 0)
    throw new Error("zero output length is invalid");
  t = Bo(t);
  const n = e * 2, r = t.toString(16);
  if (r.length > n)
    throw new RangeError("number is too large");
  return rn(r.padStart(n, "0"));
}
function hn(t, e) {
  return ln(t, e).reverse();
}
function xt(t) {
  return Uint8Array.from(at(t));
}
function ct(t) {
  return typeof t == "bigint" && Ht <= t;
}
function pn(t, e, n) {
  return ct(t) && ct(e) && ct(n) && e <= t && t < n;
}
function bt(t, e, n, r) {
  if (!pn(e, n, r))
    throw new RangeError("expected valid " + t + ": " + n + " <= n < " + r + ", got " + e);
}
function Ro(t) {
  if (t < Ht)
    throw new Error("expected non-negative bigint, got " + t);
  return t === Ht ? 0 : t.toString(2).length;
}
const vo = (t) => (ce(t, "n"), (qe << BigInt(t)) - qe);
function Dt(t, e = {}, n = {}, r = "object") {
  ut(t, r), ut(e, "fields"), ut(n, "optFields");
  function o(s, c, f) {
    const a = r === "object" ? `param "${String(s)}"` : `"${r}.${String(s)}"`, u = t[s];
    if (!Object.hasOwn(t, s) && (f ? u !== void 0 : c !== "function"))
      throw new TypeError(`${a} is invalid: expected own property`);
    if (f && u === void 0)
      return;
    const d = typeof u;
    if (d !== c || u === null)
      throw new TypeError(`${a} is invalid: expected ${c}, got ${d}`);
  }
  const i = (s, c) => Object.entries(s).forEach(([f, a]) => o(f, a, c));
  i(e, !1), i(n, !0);
}
/*! noble-curves - MIT License (c) 2022 Paul Miller (paulmillr.com) */
const N = /* @__PURE__ */ BigInt(0), _ = /* @__PURE__ */ BigInt(1), it = /* @__PURE__ */ BigInt(2), gn = /* @__PURE__ */ BigInt(3), he = /* @__PURE__ */ BigInt(4), wn = /* @__PURE__ */ BigInt(5), Oo = /* @__PURE__ */ BigInt(7), yn = /* @__PURE__ */ BigInt(8), _o = /* @__PURE__ */ BigInt(9), Ao = /* @__PURE__ */ BigInt(15), bn = /* @__PURE__ */ BigInt(16), To = /* @__PURE__ */ BigInt("0x10000000000000000");
function O(t, e) {
  if (e <= N)
    throw new Error("mod: expected positive modulus, got " + e);
  const n = t % e;
  return n >= N ? n : e + n;
}
function So(t, e, n) {
  if (n <= _)
    throw new Error("pow: expected modulus > 1, got " + n);
  if (typeof e != "bigint")
    throw new TypeError("invalid exponent: expected bigint, got " + typeof e);
  if (e < N)
    throw new Error("invalid exponent, negatives unsupported");
  if (e === N)
    return _;
  if (e === _)
    return t;
  let r = t % n;
  if (r < N && (r += n), e < To) {
    let c = _;
    for (; e > N; )
      e & _ && (c = c * r % n), r = r * r % n, e >>= _;
    return c;
  }
  const o = [];
  for (; e > N; )
    o.push(Number(e & Ao)), e >>= he;
  const i = new Array(16);
  i[0] = _, i[1] = r;
  for (let c = 2; c < 16; c++)
    i[c] = i[c - 1] * r % n;
  let s = i[o[o.length - 1]];
  for (let c = o.length - 2; c >= 0; c--) {
    s = s * s % n, s = s * s % n, s = s * s % n, s = s * s % n;
    const f = o[c];
    f !== 0 && (s = s * i[f] % n);
  }
  return s;
}
function z(t, e, n) {
  if (n <= _)
    throw new Error("pow2: expected modulus > 1, got " + n);
  if (e < N)
    throw new Error("pow2: expected non-negative exponent, got " + e);
  let r = t;
  for (; e-- > N; )
    r *= r, r %= n;
  return r;
}
function He(t, e) {
  if (t === N)
    throw new Error("invert: expected non-zero number");
  if (e <= _)
    throw new Error("invert: expected modulus > 1, got " + e);
  let n = O(t, e), r = e, o = N, i = _;
  for (; n !== N; ) {
    const c = r / n, f = r - n * c, a = o - i * c;
    r = n, n = f, o = i, i = a;
  }
  if (r !== _)
    throw new Error("invert: does not exist");
  return O(o, e);
}
function pe(t, e, n) {
  const r = t;
  if (!r.eql(r.sqr(e), n))
    throw new Error("Cannot find square root");
}
function ge(t, e) {
  if ((t & _) === N)
    throw new Error(e + ": expected odd modulus, got " + t);
}
function mn(t, e) {
  const n = t, r = (n.ORDER + _) / he, o = n.pow(e, r);
  return pe(n, o, e), o;
}
function Io(t, e) {
  const n = t, r = (n.ORDER - wn) / yn, o = n.mul(e, it), i = n.pow(o, r), s = n.mul(e, i), c = n.mul(n.mul(s, it), i), f = n.mul(s, n.sub(c, n.ONE));
  return pe(n, f, e), f;
}
function Lo(t) {
  const e = we(t), n = En(t), r = n(e, e.neg(e.ONE)), o = n(e, r), i = n(e, e.neg(r)), s = (t + Oo) / bn;
  return ((c, f) => {
    const a = c;
    let u = a.pow(f, s), d = a.mul(u, r);
    const l = a.mul(u, o), h = a.mul(u, i), w = a.eql(a.sqr(d), f), b = a.eql(a.sqr(l), f);
    u = a.cmov(u, d, w), d = a.cmov(h, l, b);
    const x = a.eql(a.sqr(d), f), R = a.cmov(u, d, x);
    return pe(a, R, f), R;
  });
}
function En(t) {
  if (t < gn)
    throw new Error("sqrt is not defined for small field");
  ge(t, "tonelliShanks");
  let e = t - _, n = 0;
  for (; e % it === N; )
    e /= it, n++;
  let r = it;
  const o = we(t);
  for (; kt(o, r) === 1; )
    if (r++ > 1e3)
      throw new Error("Cannot find square root: probably non-prime P");
  if (n === 1)
    return mn;
  let i = o.pow(r, e);
  const s = (e + _) / it;
  return function(f, a) {
    const u = f;
    if (u.is0(a))
      return a;
    if (kt(u, a) !== 1)
      throw new Error("Cannot find square root");
    let d = n, l = u.mul(u.ONE, i), h = u.pow(a, e), w = u.pow(a, s);
    for (; !u.eql(h, u.ONE); ) {
      if (u.is0(h))
        throw new Error("Cannot find square root: probably non-prime P");
      let b = 1, x = u.sqr(h);
      for (; !u.eql(x, u.ONE); )
        if (b++, x = u.sqr(x), b === d)
          throw new Error("Cannot find square root");
      const R = _ << BigInt(d - b - 1), y = u.pow(l, R);
      d = b, l = u.sqr(y), h = u.mul(h, l), w = u.mul(w, y);
    }
    return w;
  };
}
function Uo(t) {
  return ge(t, "Fp.sqrt"), t % he === gn ? mn : t % yn === wn ? Io : t % bn === _o ? Lo(t) : En(t);
}
const Co = (t, e) => (O(t, e) & _) === _, $o = [
  "create",
  "isValid",
  "is0",
  "neg",
  "inv",
  "sqrt",
  "sqr",
  "eql",
  "add",
  "sub",
  "mul",
  "pow",
  "div",
  "addN",
  "subN",
  "mulN",
  "sqrN"
];
function Bt(t) {
  if (ut(t, "field"), typeof t.ORDER != "bigint")
    throw new TypeError('param "ORDER" is invalid: expected bigint, got ' + typeof t.ORDER);
  ce(t.BYTES, "BYTES"), ce(t.BITS, "BITS");
  for (const e of $o)
    yt(t[e], "field." + e);
  if (t.BYTES < 1 || t.BITS < 1)
    throw new Error("invalid field: expected BYTES/BITS > 0");
  if (t.ORDER <= _)
    throw new Error("invalid field: expected ORDER > 1, got " + t.ORDER);
  return t;
}
function xn(t, e, n = !1) {
  Bt(t), sn(e, "nums"), Yt(n, "passZero");
  const r = t, o = new Array(e.length).fill(n ? r.ZERO : void 0), i = e.reduce((c, f, a) => r.is0(f) ? c : (o[a] = c, r.mul(c, f)), r.ONE), s = r.inv(i);
  return e.reduceRight((c, f, a) => r.is0(f) ? c : (o[a] = r.mul(c, o[a]), r.mul(c, f)), s), o;
}
function kt(t, e) {
  Bt(t);
  const n = t;
  ge(n.ORDER, "FpLegendre");
  const r = (n.ORDER - _) / it, o = n.pow(e, r), i = n.eql(o, n.ONE), s = n.eql(o, n.ZERO), c = n.eql(o, n.neg(n.ONE));
  if (!i && !s && !c)
    throw new Error("invalid Legendre symbol result");
  return i ? 1 : s ? 0 : -1;
}
function No(t, e) {
  if (e !== void 0 && cn(e), t <= N)
    throw new Error("invalid n length: expected positive n, got " + t);
  if (e !== void 0 && e < 1)
    throw new Error("invalid n length: expected positive bit length, got " + e);
  const n = Ro(t);
  if (e !== void 0 && e < n)
    throw new Error(`invalid n length: expected nBitLength (${e}) >= bitLen(n) (${n})`);
  const r = e !== void 0 ? e : n, o = Math.ceil(r / 8);
  return { nBitLength: r, nByteLength: o };
}
const Fe = /* @__PURE__ */ new WeakMap();
class De {
  constructor(e, n = {}) {
    g(this, "ORDER");
    g(this, "BITS");
    g(this, "BYTES");
    g(this, "isLE");
    g(this, "ZERO", N);
    g(this, "ONE", _);
    g(this, "_lengths");
    g(this, "_mod");
    if (e <= _)
      throw new Error("invalid field: expected ORDER > 1, got " + e);
    let r;
    this.isLE = !1, n != null && typeof n == "object" && (typeof n.BITS == "number" && (r = n.BITS), typeof n.sqrt == "function" && Object.defineProperty(this, "sqrt", { value: n.sqrt, enumerable: !0 }), typeof n.isLE == "boolean" && (this.isLE = n.isLE), n.allowedLengths && (this._lengths = Object.freeze(n.allowedLengths.slice())), typeof n.modFromBytes == "boolean" && (this._mod = n.modFromBytes));
    const { nBitLength: o, nByteLength: i } = No(e, r);
    if (i > 2048)
      throw new Error("invalid field: expected ORDER of <= 2048 bytes");
    this.ORDER = e, this.BITS = o, this.BYTES = i, Object.freeze(this);
  }
  create(e) {
    return O(e, this.ORDER);
  }
  isValid(e) {
    if (typeof e != "bigint")
      throw new TypeError("invalid field element: expected bigint, got " + typeof e);
    return N <= e && e < this.ORDER;
  }
  is0(e) {
    return e === N;
  }
  // is valid and invertible
  isValidNot0(e) {
    return !this.is0(e) && this.isValid(e);
  }
  isOdd(e) {
    return (e & _) === _;
  }
  neg(e) {
    return O(-e, this.ORDER);
  }
  eql(e, n) {
    return e === n;
  }
  sqr(e) {
    return O(e * e, this.ORDER);
  }
  add(e, n) {
    return O(e + n, this.ORDER);
  }
  sub(e, n) {
    return O(e - n, this.ORDER);
  }
  mul(e, n) {
    return O(e * n, this.ORDER);
  }
  pow(e, n) {
    return So(e, n, this.ORDER);
  }
  div(e, n) {
    return O(e * He(n, this.ORDER), this.ORDER);
  }
  // Same as above, but doesn't normalize
  sqrN(e) {
    return e * e;
  }
  addN(e, n) {
    return e + n;
  }
  subN(e, n) {
    return e - n;
  }
  mulN(e, n) {
    return e * n;
  }
  inv(e) {
    return He(e, this.ORDER);
  }
  sqrt(e) {
    let n = Fe.get(this);
    return n || Fe.set(this, n = Uo(this.ORDER)), n(this, e);
  }
  toBytes(e) {
    return this.isLE ? hn(e, this.BYTES) : ln(e, this.BYTES);
  }
  fromBytes(e, n = !1) {
    at(e);
    const { _lengths: r, BYTES: o, isLE: i, ORDER: s, _mod: c } = this;
    if (r) {
      if (e.length < 1 || !r.includes(e.length) || e.length > o)
        throw new Error("Field.fromBytes: expected " + r + " bytes, got " + e.length);
      const a = new Uint8Array(o);
      a.set(e, i ? 0 : a.length - e.length), e = a;
    }
    if (e.length !== o)
      throw new Error("Field.fromBytes: expected " + o + " bytes, got " + e.length);
    let f = i ? Ft(e) : dn(e);
    if (c && (f = O(f, s)), !n && !this.isValid(f))
      throw new Error("invalid field element: outside of range 0..ORDER");
    return f;
  }
  // TODO: we don't need it here, move out to separate fn
  invertBatch(e) {
    return xn(this, e, !0);
  }
  // We can't move this out because Fp6, Fp12 implement it
  // and it's unclear what to return in there.
  cmov(e, n, r) {
    return Yt(r, "condition"), r ? n : e;
  }
}
function we(t, e = {}) {
  return Object.freeze(De.prototype), new De(t, e);
}
/*! noble-curves - MIT License (c) 2022 Paul Miller (paulmillr.com) */
const ye = /* @__PURE__ */ BigInt(0), Rt = /* @__PURE__ */ BigInt(1), qo = /* @__PURE__ */ BigInt(4), te = 16, ke = 128, Ho = 5, Me = 2 ** 31;
function be(t) {
  const e = t;
  if (typeof e != "function")
    throw new TypeError('"Point" expected constructor, got type=' + typeof t);
  yt(e.fromAffine, "Point.fromAffine"), yt(e.fromBytes, "Point.fromBytes"), yt(e.fromHex, "Point.fromHex"), ut(e.BASE, "Point.BASE"), ut(e.ZERO, "Point.ZERO"), Bt(e.Fp), Bt(e.Fn);
}
function Fo(t, e) {
  be(t), Bn(e, t);
  const n = xn(t.Fp, e.map((r) => r.Z));
  return e.map((r, o) => t.fromAffine(r.toAffine(n[o])));
}
function Do(t, e, n = 1) {
  if (!Number.isSafeInteger(t) || t < n || t > e)
    throw new Error("invalid window size, expected [" + n + ".." + e + "], got W=" + t);
}
function ko(t, e) {
  const n = t * (4 * e + 128);
  if (n > Me)
    throw new Error("invalid window size: table would need ~" + Math.ceil(n / 2 ** 20) + " MiB, max " + Me / 2 ** 20 + " MiB");
}
function Mo(t, e) {
  if (t !== void 0) {
    yt(t, "randomBytes");
    try {
      const n = t(e);
      if (!fn(n) || n.length !== e)
        return;
    } catch {
      return;
    }
    return t;
  }
}
function Bn(t, e) {
  sn(t, "points"), t.forEach((n, r) => {
    if (!(n instanceof e))
      throw new Error("invalid point at index " + r);
  });
}
function Zo(t, e, n) {
  if (!Array.isArray(t))
    throw new Error("array of scalars expected");
  t.forEach((r, o) => {
    if (!(n === void 0 ? e.isValid(r) : ct(r) && r < n))
      throw new Error("invalid scalar at index " + o);
  });
}
const Rn = /* @__PURE__ */ new WeakMap();
function ee(t) {
  return Rn.get(t) || 1;
}
function Po(t, e) {
  const n = t.double(), r = [t];
  for (let o = 1; o < e; o++)
    r.push(r[o - 1].add(n));
  return r;
}
function jo(t, e) {
  const n = 2 ** e, r = n / 2, o = BigInt(n - 1), i = [];
  for (; t > ye; ) {
    let s = 0;
    t & Rt && (s = Number(t & o), s >= r && (s -= n), t -= BigInt(s)), i.push(s), t >>= Rt;
  }
  return i;
}
function Yo(t, e, n) {
  const r = 2 ** e, o = r / 2, i = BigInt(r - 1), s = BigInt(e), c = [];
  for (let f = 0; f < n; f++) {
    let a = Number(t & i);
    t >>= s, a > o && (a -= r, t += Rt), c.push(a);
  }
  if (t !== ye)
    throw new Error("invalid wnaf");
  return c;
}
function zo(t, e, n) {
  let r = 0;
  for (const i of n)
    r = Math.max(r, i.length);
  let o = t;
  for (let i = r - 1; i >= 0; i--) {
    i !== r - 1 && (o = o.double());
    for (let s = 0; s < n.length; s++) {
      const c = n[s][i];
      if (c) {
        const f = e[s][Math.abs(c) - 1 >> 1];
        o = o.add(c < 0 ? f.negate() : f);
      }
    }
  }
  return o;
}
class Xo {
  // Parametrized with a given Point class (not individual point)
  constructor(e, n) {
    g(this, "Point");
    g(this, "BASE");
    g(this, "ZERO");
    g(this, "randomBytes");
    g(this, "wnafPrecomputes", /* @__PURE__ */ new WeakMap());
    g(this, "baseCanBeBlinded");
    g(this, "bits");
    be(e), this.randomBytes = Mo(n, te), this.Point = e, this.BASE = e.BASE, this.ZERO = e.ZERO, this.bits = e.Fn.BITS;
  }
  /**
   * Creates a signed fixed-window wNAF precomputation table: for every window w, the
   * multiples `[1..2^(W−1)]⋅2^(w⋅W)⋅P`, flattened. All doublings are baked into the table,
   * so cached multiplication is additions-only. `windows = ceil(bits/W) + 1`: the extra
   * window absorbs the final carry of signed-digit recoding.
   * For a 256-bit curve and W=6, the table is 44⋅32 = 1408 points.
   * @param point - Point instance
   * @param W - window size
   * @param bits - scalar bitlength the table must cover
   */
  buildWnafTable(e, n, r) {
    const o = Math.ceil(r / n) + 1, i = 2 ** (n - 1), s = [];
    let c = e;
    for (let f = 0; f < o; f++) {
      let a = c;
      for (let u = 0; u < i; u++)
        s.push(a), a = a.add(c);
      c = s[s.length - 1].double();
    }
    return { W: n, bits: r, windows: o, comp: s };
  }
  /**
   * Implements ec multiplication using precomputed signed fixed-window wNAF tables.
   * Constant-time: fixed window count with one table addition per window — zero digits feed
   * the fake accumulator — and no doublings; the lookup scans the whole window slice.
   * Scalar bounds are validated by the public entry points ({@link ScalarMultiplier.mulCT},
   * {@link ScalarMultiplier.mulCTBlinded}, {@link ScalarMultiplier.mulUnsafe});
   * signedWindowDigits throws if `n` exceeds the table.
   * @returns real and fake (for const-time) points
   */
  wnafCachedCT(e, n) {
    const { W: r, windows: o, comp: i } = e, s = 2 ** (r - 1), c = Yo(n, r, o);
    let f = this.ZERO, a = this.BASE;
    for (let u = 0; u < o; u++) {
      const d = c[u], l = u * s, h = Math.abs(d) - 1;
      let w = i[l];
      for (let x = 1; x < s; x++)
        w = x === h ? i[l + x] : w;
      const b = w.negate();
      d === 0 ? a = a.add(i[l]) : f = f.add(d < 0 ? b : w);
    }
    return { p: f, f: a };
  }
  // Cache key is point identity plus (W, bits); at most two entries exist per point (public-width
  // `Fn.BITS` and blinded `Fn.BITS + BLIND_BITS`). Callers must not reuse the same point with
  // incompatible `transform(...)` layouts and expect a separate cache entry.
  getWnafPrecomputes(e, n, r, o) {
    let i = this.wnafPrecomputes.get(n), s = i == null ? void 0 : i.find((c) => c.W === e && c.bits === r);
    return s || (s = this.buildWnafTable(n, e, r), typeof o == "function" && (s = { ...s, comp: o(s.comp) }), i || (i = [], this.wnafPrecomputes.set(n, i)), i.push(s)), s;
  }
  assertPoint(e) {
    if (!(e instanceof this.Point))
      throw new TypeError('"point" expected Point instance, got type=' + typeof e);
  }
  // Shared prologue of the constant-time entry points. Rejects scalar 0: in key/signature-style
  // callers a zero scalar means broken upstream plumbing, and concrete Points already reject it.
  // Uses inRange instead of Fn.isValidNot0: validateField() only certifies the arithmetic subset.
  validateMulInput(e, n) {
    if (this.assertPoint(e), !pn(n, Rt, this.Point.Fn.ORDER))
      throw new Error("invalid scalar");
  }
  // Constant-time dispatch shared by mulCT / mulCTBlinded. Un-precomputed points (W===1, e.g.
  // ECDH peer keys) skip building a throwaway cached table in favor of a small fixed-window
  // multiply. `n` must be < 2^bits.
  runCT(e, n, r, o) {
    const i = ee(e);
    return i === 1 ? this.fixedWindowCT(e, n, r) : this.wnafCachedCT(this.getWnafPrecomputes(i, e, r, o), n);
  }
  mulCT(e, n, r) {
    return this.validateMulInput(e, n), this.runCT(e, n, this.bits, r);
  }
  mulCTBlinded(e, n, r) {
    if (this.validateMulInput(e, n), this.randomBytes === void 0)
      throw new Error("randomBytes is required for scalar blinding");
    const o = this.Point.Fn.BITS + ke, i = this.randomBytes(te);
    if (!fn(i) || i.length !== te)
      throw new Error("randomBytes returned invalid byte array");
    i[0] = i[0] & 63 | 128;
    const s = n + dn(i) * this.Point.Fn.ORDER;
    return this.runCT(e, s, o, r);
  }
  /**
   * Constant-time multiplication `n*point` for an un-precomputed point, via a small fixed window.
   * A cached wNAF table only pays off when reused; a flat 2^FW_WINDOW table (`size-1` adds) is
   * far cheaper to build for a single use. The point-operation sequence is independent of `n`:
   * build the table, then per window exactly FW_WINDOW doublings, a data-oblivious scan over
   * every table entry, and one addition (adds the identity when the window digit is 0 — never
   * skipped).
   *
   * `n` must be `< 2^bits`. Assumes complete addition (adding the identity costs the same as any
   * add), which holds for the Weierstrass/Edwards point types used here. The table is left in
   * projective form (no normalizeZ): normalizing this small a table costs more than the
   * mixed-add savings it would buy for a single multiply.
   * @returns real point `p`; `f` duplicates it only to match {@link wnafCachedCT}'s return shape
   * (this path needs no fake accumulator — its op-count is already scalar-independent).
   */
  fixedWindowCT(e, n, r) {
    const o = Ho, i = 1 << o, s = vo(o), c = new Array(i);
    c[0] = this.ZERO;
    for (let u = 1; u < i; u++)
      c[u] = c[u - 1].add(e);
    const f = Math.ceil(r / o);
    let a = this.ZERO;
    for (let u = f - 1; u >= 0; u--) {
      if (u !== f - 1)
        for (let h = 0; h < o; h++)
          a = a.double();
      const d = Number(n >> BigInt(u * o) & s);
      let l = c[0];
      for (let h = 1; h < i; h++)
        l = h === d ? c[h] : l;
      a = a.add(l);
    }
    return { p: a, f: a };
  }
  shouldBlind(e, n) {
    return this.randomBytes === void 0 ? !1 : n === Rt ? !0 : e !== this.BASE ? !1 : (this.baseCanBeBlinded === void 0 && (this.baseCanBeBlinded = this.mulUnsafe(this.BASE, this.Point.Fn.ORDER).is0()), this.baseCanBeBlinded);
  }
  mulSecret(e, n, r, o) {
    return this.shouldBlind(e, r) ? this.mulCTBlinded(e, n, o) : this.mulCT(e, n, o);
  }
  mulUnsafe(e, n, r) {
    if (this.assertPoint(e), !ct(n))
      throw new Error("invalid scalar");
    const o = ee(e);
    if (o === 1 || n >= this.Point.Fn.ORDER)
      return Wo(this.Point, [e], [n], !0);
    const i = this.getWnafPrecomputes(o, e, this.bits, r);
    return this.wnafCachedCT(i, n).p;
  }
  // Remembers the window size used for precomputed wNAF multiplication of the given point
  // and drops any previously built tables. Usually only the base point is precomputed.
  // W=1 resets the point to the un-precomputed (table-less) paths.
  // W is additionally capped so tables stay under ~2 GiB ({@link TABLE_BYTES_MAX}).
  setWindowSize(e, n) {
    this.assertPoint(e), Do(n, this.bits);
    const r = Math.ceil((this.bits + ke) / n) + 1;
    ko(r * 2 ** (n - 1), this.Point.Fp.BYTES), Rn.set(e, n), this.wnafPrecomputes.delete(e);
  }
  // True when a window size is set: tables themselves are built lazily on first multiply.
  hasWindowSize(e) {
    return ee(e) !== 1;
  }
}
function Wo(t, e, n, r = !1) {
  if (be(t), Bn(e, t), Yt(r, "allowOversized"), Zo(n, t.Fn, r ? t.Fn.ORDER ** qo : void 0), e.length !== n.length)
    throw new Error("arrays of points and scalars must have equal length");
  const o = e.map((s) => Po(s, 4)), i = n.map((s) => jo(s, 4));
  return zo(t.ZERO, o, i);
}
function Ze(t, e, n) {
  if (e) {
    if (e.ORDER !== t)
      throw new Error("Field.ORDER must match order: Fp == p, Fn == n");
    return Bt(e), e;
  } else
    return we(t, { isLE: n });
}
function Ko(t, e, n = {}, r) {
  if (r === void 0 && (r = t === "edwards"), !e || typeof e != "object")
    throw new Error(`expected valid ${t} CURVE object`);
  Dt(n);
  for (const f of ["p", "n", "h"]) {
    const a = e[f];
    if (!(ct(a) && a !== ye))
      throw new Error(`CURVE.${f} must be positive bigint`);
  }
  const o = Ze(e.p, n.Fp, r), i = Ze(e.n, n.Fn, r), c = ["Gx", "Gy", "a", "d"];
  for (const f of c)
    if (!o.isValid(e[f]))
      throw new Error(`CURVE.${f} must be valid field element of CURVE.Fp`);
  return e = Object.freeze(Object.assign({}, e)), { CURVE: e, Fp: o, Fn: i };
}
function Vo(t, e) {
  return function(r) {
    const o = t(r);
    return { secretKey: o, publicKey: e(o) };
  };
}
/*! noble-curves - MIT License (c) 2022 Paul Miller (paulmillr.com) */
const It = /* @__PURE__ */ BigInt(0), Lt = /* @__PURE__ */ BigInt(1), Ut = /* @__PURE__ */ BigInt(2), Go = /* @__PURE__ */ BigInt(4), Pe = /* @__PURE__ */ BigInt(8);
function Jo(t, e, n, r) {
  const o = t.sqr(n), i = t.sqr(r), s = t.add(t.mul(e.a, o), i), c = t.add(t.ONE, t.mul(e.d, t.mul(o, i)));
  return t.eql(s, c);
}
function Qo(t, e = {}) {
  Dt(e, {}, {}, "extraOpts");
  const n = e, r = Ko("edwards", t, n, n.FpFnLE), { Fp: o, Fn: i } = r;
  let s = r.CURVE;
  const { h: c } = s;
  if (kt(o, s.a) !== 1)
    throw new Error("edwards: CURVE.a must be a square in Fp for complete addition formulas");
  if (kt(o, s.d) !== -1)
    throw new Error("edwards: CURVE.d must be a non-square in Fp for complete addition formulas");
  Dt(n, {}, { uvRatio: "function", randomBytes: "function" });
  const f = n.randomBytes === void 0 ? an : n.randomBytes, a = Ut << BigInt(o.BYTES * 8) - Lt;
  function u(v) {
    if (!o.isOdd)
      throw new Error("Field does not have .isOdd()");
    return o.isOdd(v);
  }
  const d = n.uvRatio === void 0 ? (v, p) => {
    try {
      return { isValid: !0, value: o.sqrt(o.div(v, p)) };
    } catch {
      return { isValid: !1, value: It };
    }
  } : n.uvRatio;
  if (!Jo(o, s, s.Gx, s.Gy))
    throw new Error("bad curve params: generator point");
  const l = o.eql(s.a, o.neg(o.ONE)) ? (v) => o.neg(v) : o.eql(s.a, o.ONE) ? (v) => v : (v) => o.mul(s.a, v);
  function h(v, p, E = !1) {
    const m = E ? Lt : It;
    return bt("coordinate " + v, p, m, a), p;
  }
  function w(v) {
    if (!(v instanceof b))
      throw new Error("EdwardsPoint expected");
  }
  const y = class y {
    constructor(p, E, m, T) {
      g(this, "X");
      g(this, "Y");
      g(this, "Z");
      g(this, "T");
      this.X = h("x", p), this.Y = h("y", E), this.Z = h("z", m, !0), this.T = h("t", T), Object.freeze(this);
    }
    static CURVE() {
      return s;
    }
    /**
     * Create one extended Edwards point from affine coordinates.
     * Does NOT validate that the point is on-curve or torsion-free.
     * Use `.assertValidity()` on adversarial inputs.
     */
    static fromAffine(p) {
      if (p instanceof y)
        throw new Error("extended point not allowed");
      const { x: E, y: m } = p || {};
      return h("x", E), h("y", m), new y(E, m, o.ONE, o.mul(E, m));
    }
    // Uses algo from RFC8032 5.1.3.
    static fromBytes(p, E = !1) {
      const m = o.BYTES, { a: T, d: S } = s;
      p = xt(at(p, m, "point")), Yt(E, "zip215");
      const L = xt(p), U = p[m - 1];
      L[m - 1] = U & -129;
      const q = Ft(L), F = E ? a : o.ORDER;
      bt("point.y", q, It, F);
      const C = o.sqr(q), D = o.sub(C, o.ONE), M = o.sub(o.mulN(S, C), T);
      let { isValid: B, value: A } = d(D, M);
      if (!B)
        throw new Error("bad point: invalid y coordinate");
      const $ = u(A), k = (U & 128) !== 0;
      if (!E && o.is0(A) && k)
        throw new Error("bad point: x=0 and x_0=1");
      return k !== $ && (A = o.neg(A)), y.fromAffine({ x: A, y: q });
    }
    static fromHex(p, E = !1) {
      return y.fromBytes(Eo(p), E);
    }
    get x() {
      return this.toAffine().x;
    }
    get y() {
      return this.toAffine().y;
    }
    precompute(p = 6, E = !0) {
      return R.setWindowSize(this, p), E || this.multiply(Ut), this;
    }
    // Useful in fromAffine() - not for fromBytes(), which always created valid points.
    assertValidity() {
      const p = this, { a: E, d: m } = s;
      if (p.is0())
        throw new Error("bad point: ZERO");
      const { X: T, Y: S, Z: L, T: U } = p, q = o.sqr(T), F = o.sqr(S), C = o.sqr(L), D = o.sqr(C), M = o.mul(q, E), B = o.mul(o.add(M, F), C), A = o.add(D, o.mul(m, o.mul(q, F)));
      if (!o.eql(B, A))
        throw new Error("bad point: equation left != right (1)");
      const $ = o.mul(T, S), k = o.mul(L, U);
      if (!o.eql($, k))
        throw new Error("bad point: equation left != right (2)");
    }
    // Compare one point to another.
    equals(p) {
      w(p);
      const { X: E, Y: m, Z: T } = this, { X: S, Y: L, Z: U } = p, q = o.mul(E, U), F = o.mul(S, T), C = o.mul(m, U), D = o.mul(L, T);
      return o.eql(q, F) && o.eql(C, D);
    }
    is0() {
      return this.equals(y.ZERO);
    }
    negate() {
      return new y(o.neg(this.X), this.Y, this.Z, o.neg(this.T));
    }
    // Fast algo for doubling Extended Point.
    // https://hyperelliptic.org/EFD/g1p/auto-twisted-extended.html#doubling-dbl-2008-hwcd
    // Cost: 4M + 4S + 1*a + 6add + 1*2.
    double() {
      const { X: p, Y: E, Z: m } = this, T = o.sqr(p), S = o.sqr(E), L = o.mul(o.sqr(m), Ut), U = l(T), q = o.addN(p, E), F = o.sub(o.subN(o.sqr(q), T), S), C = o.addN(U, S), D = o.subN(C, L), M = o.subN(U, S), B = o.mul(F, D), A = o.mul(C, M), $ = o.mul(F, M), k = o.mul(D, C);
      return new y(B, A, k, $);
    }
    // Fast algo for adding 2 Extended Points.
    // https://hyperelliptic.org/EFD/g1p/auto-twisted-extended.html#addition-add-2008-hwcd
    // Cost: 9M + 1*a + 1*d + 7add.
    add(p) {
      w(p);
      const { d: E } = s, { X: m, Y: T, Z: S, T: L } = this, { X: U, Y: q, Z: F, T: C } = p, D = o.mul(m, U), M = o.mul(T, q), B = o.mul(o.mulN(L, E), C), A = o.mul(S, F), $ = o.sub(o.subN(o.mulN(o.addN(m, T), o.addN(U, q)), D), M), k = o.subN(A, B), j = o.addN(A, B), Y = o.sub(M, l(D)), V = o.mul($, k), G = o.mul(j, Y), Xt = o.mul($, Y), Ot = o.mul(k, j);
      return new y(V, G, Ot, Xt);
    }
    subtract(p) {
      return w(p), this.add(p.negate());
    }
    // Constant-time multiplication.
    multiply(p) {
      if (!i.isValidNot0(p))
        throw new RangeError("invalid scalar: expected 1 <= sc < curve.n");
      const { p: E, f: m } = R.mulSecret(this, p, c, x);
      return x([E, m])[0];
    }
    // Non-constant-time multiplication. Uses double-and-add algorithm.
    // It's faster, but should only be used when you don't care about
    // an exposed private key e.g. sig verification.
    // Keeps the same subgroup-scalar contract: 0 is allowed for public-scalar callers, but
    // n and larger values are rejected instead of being reduced mod n to the identity point.
    multiplyUnsafe(p) {
      if (!i.isValid(p))
        throw new RangeError("invalid scalar: expected 0 <= sc < curve.n");
      return p === It ? y.ZERO : this.is0() || p === Lt ? this : R.mulUnsafe(this, p, x);
    }
    // Checks if point is of small order.
    // If you add something to small order point, you will have "dirty"
    // point with torsion component.
    // Clears cofactor and checks if the result is 0.
    isSmallOrder() {
      return this.clearCofactor().is0();
    }
    // Multiplies point by curve order and checks if the result is 0.
    // Returns `false` is the point is dirty.
    isTorsionFree() {
      return R.mulUnsafe(this, s.n).is0();
    }
    // Converts Extended point to default (x, y) coordinates.
    // Can accept precomputed Z^-1 - for example, from invertBatch.
    toAffine(p) {
      const E = this;
      let m = p;
      if (m != null && typeof m != "bigint")
        throw new TypeError('"invertedZ" expected bigint, got type=' + typeof m);
      const { X: T, Y: S, Z: L } = E, U = E.is0();
      m == null && (m = U ? o.create(Pe) : o.inv(L));
      const q = o.mul(T, m), F = o.mul(S, m), C = o.mul(L, m);
      if (U)
        return { x: o.ZERO, y: o.ONE };
      if (!o.eql(C, o.ONE))
        throw new Error("invZ was invalid");
      return { x: q, y: F };
    }
    clearCofactor() {
      return c === Lt ? this : c === Ut ? this.double() : c === Go ? this.double().double() : c === Pe ? this.double().double().double() : this.multiplyUnsafe(c);
    }
    toBytes() {
      const { x: p, y: E } = this.toAffine(), m = o.toBytes(E);
      return m[m.length - 1] |= u(p) ? 128 : 0, m;
    }
    toHex() {
      return mo(this.toBytes());
    }
    toString() {
      return `<Point ${this.is0() ? "ZERO" : this.toHex()}>`;
    }
  };
  g(y, "BASE", new y(s.Gx, s.Gy, o.ONE, o.mul(s.Gx, s.Gy))), g(y, "ZERO", new y(o.ZERO, o.ONE, o.ONE, o.ZERO)), g(y, "Fp", o), g(y, "Fn", i);
  let b = y;
  const x = (v) => Fo(b, v), R = new Xo(b, f);
  return R.bits >= 6 && b.BASE.precompute(6), Object.freeze(b.prototype), Object.freeze(b), b;
}
/*! noble-curves - MIT License (c) 2022 Paul Miller (paulmillr.com) */
const ot = /* @__PURE__ */ BigInt(0), Z = /* @__PURE__ */ BigInt(1), Ct = /* @__PURE__ */ BigInt(2);
function je(t, e) {
  return t + e - (e >> Z << Z);
}
function tr(t) {
  const e = BigInt(6) * t;
  return (n, r, o) => {
    const i = r + o, c = ((e + o - r) * n + r) % t;
    return { x_2: c, x_3: i - c };
  };
}
function er(t) {
  return Dt(t, {
    P: "bigint",
    type: "string",
    adjustScalarBytes: "function",
    powPminus2: "function"
  }, {
    randomBytes: "function",
    scalarMultBase: "function"
  }), Object.freeze({ ...t });
}
function nr(t) {
  const e = er(t), { P: n, type: r, adjustScalarBytes: o, powPminus2: i, randomBytes: s } = e, c = e.scalarMultBase, f = r === "x25519";
  if (!f && r !== "x448")
    throw new Error("invalid type");
  const a = s === void 0 ? an : s, u = f ? 255 : 448, d = tr(n), l = f ? 32 : 56, h = BigInt(f ? 9 : 5), w = BigInt(f ? 121665 : 39081), b = f ? Ct ** BigInt(254) : Ct ** BigInt(447), x = f ? BigInt(8) * (Ct ** BigInt(251) - Z) : BigInt(4) * (Ct ** BigInt(445) - Z), R = b + x + Z, y = (B) => O(B, n), v = p(h);
  function p(B) {
    return hn(y(B), l);
  }
  function E(B) {
    const A = xt(at(B, l, "uCoordinate"));
    return f && (A[31] &= 127), y(Ft(A));
  }
  function m(B) {
    return Ft(o(xt(at(B, l, "scalar"))));
  }
  const T = new Set(f ? [
    ot,
    Z,
    n - Z,
    BigInt("325606250916557431795983626356110631294008115727848805560023387167927233504"),
    BigInt("39382357235489614581723060781553021112529911719440698176882885853963445705823")
  ] : [ot, Z, n - Z]);
  function S(B, A) {
    const $ = E(A);
    if (T.has($))
      throw new Error("invalid private or public key received");
    const k = F($, m(B));
    if (k === ot)
      throw new Error("invalid private or public key received");
    return p(k);
  }
  function L(B) {
    if (c === void 0)
      return S(B, v);
    const A = m(B);
    bt("scalar", A, b, R);
    const $ = y(c(A));
    if ($ === ot)
      throw new Error("invalid private or public key received");
    return p($);
  }
  const U = L, q = S;
  function F(B, A) {
    bt("u", B, ot, n), bt("scalar", A, b, R);
    const $ = A, k = B;
    let j = Z, Y = ot, V = B, G = Z;
    const Xt = $ ^ $ >> Z;
    for (let Wt = BigInt(u - 1); Wt >= ot; Wt--) {
      const Be = je(n, Xt >> Wt);
      ({ x_2: j, x_3: V } = d(Be, j, V)), { x_2: Y, x_3: G } = d(Be, Y, G);
      const Kt = j + Y, Vt = y(Kt * Kt), Gt = j - Y, Re = y(Gt * Gt), ve = Vt - Re, In = V + G, Ln = V - G, Oe = y(Ln * Kt), _e = y(In * Gt), Ae = Oe + _e, Te = Oe - _e;
      V = y(Ae * Ae), G = y(k * y(Te * Te)), j = y(Vt * Re), Y = y(ve * (Vt + y(w * ve)));
    }
    const Ot = je(n, $);
    ({ x_2: j, x_3: V } = d(Ot, j, V)), { x_2: Y, x_3: G } = d(Ot, Y, G);
    const Sn = i(Y);
    return y(j * Sn);
  }
  const C = {
    secretKey: l,
    publicKey: l,
    seed: l
  }, D = (B) => (B = B === void 0 ? a(l) : B, at(B, C.seed, "seed"), B), M = { randomSecretKey: D };
  return Object.freeze(C), Object.freeze(M), Object.freeze({
    keygen: Vo(D, U),
    getSharedSecret: q,
    getPublicKey: U,
    scalarMult: S,
    scalarMultBase: L,
    utils: M,
    GuBytes: v.slice(),
    lengths: C
  });
}
/*! noble-curves - MIT License (c) 2022 Paul Miller (paulmillr.com) */
const Ye = /* @__PURE__ */ BigInt(0), or = /* @__PURE__ */ BigInt(1), ze = /* @__PURE__ */ BigInt(2), rr = /* @__PURE__ */ BigInt(3), ir = /* @__PURE__ */ BigInt(5), sr = /* @__PURE__ */ BigInt(8), zt = /* @__PURE__ */ BigInt("0x7fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffed"), cr = {
  p: zt,
  n: BigInt("0x1000000000000000000000000000000014def9dea2f79cd65812631a5cf5d3ed"),
  h: sr,
  a: BigInt("0x7fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffec"),
  d: BigInt("0x52036cee2b6ffe738cc740797779e89800700a4d4141d8ab75eb4dca135978a3"),
  Gx: BigInt("0x216936d3cd6e53fec0a4e231fdd6dc5c692cc7609525a7b2c9562d608f25d51a"),
  Gy: BigInt("0x6666666666666666666666666666666666666666666666666666666666666658")
};
function vn(t) {
  const e = BigInt(10), n = BigInt(20), r = BigInt(40), o = BigInt(80), i = zt, c = t * t % i * t % i, f = z(c, ze, i) * c % i, a = z(f, or, i) * t % i, u = z(a, ir, i) * a % i, d = z(u, e, i) * u % i, l = z(d, n, i) * d % i, h = z(l, r, i) * l % i, w = z(h, o, i) * h % i, b = z(w, o, i) * h % i, x = z(b, e, i) * u % i;
  return { pow_p_5_8: z(x, ze, i) * t % i, b2: c };
}
function fr(t) {
  return t[0] &= 248, t[31] &= 127, t[31] |= 64, t;
}
const Xe = /* @__PURE__ */ BigInt("19681161376707505956807079304988542015446066515923890162744021073123829784752");
function ar(t, e) {
  const n = zt, r = O(e * e * e, n), o = O(r * r * e, n), i = vn(t * o).pow_p_5_8;
  let s = O(t * r * i, n);
  const c = O(e * s * s, n), f = s, a = O(s * Xe, n), u = c === t, d = c === O(-t, n), l = c === O(-t * Xe, n);
  return u && (s = f), (d || l) && (s = a), Co(s, n) && (s = O(-s, n)), { isValid: u || d, value: s };
}
const We = /* @__PURE__ */ Qo(cr, { uvRatio: ar }), Ke = /* @__PURE__ */ (() => {
  const t = zt, e = (n) => {
    const { pow_p_5_8: r, b2: o } = vn(n);
    return O(z(r, rr, t) * o, t);
  };
  return nr({
    P: t,
    type: "x25519",
    powPminus2: e,
    adjustScalarBytes: fr,
    // ~3x faster fixed-base: [k]B on the birationally-equivalent Edwards curve using cached
    // base tables, mapped back via u = (1+y)/(1-y) = (Z+Y)/(Z-Y) with one Fermat inversion.
    // Same construction as libsodium's crypto_scalarmult_curve25519_base.
    scalarMultBase: (n) => {
      const r = O(n, We.Fn.ORDER);
      if (r === Ye)
        return Ye;
      const o = We.BASE.multiply(r);
      return O((o.Z + o.Y) * e(O(o.Z - o.Y, t)), t);
    }
  });
})();
class Ve {
  constructor(e, n) {
    g(this, "oHash");
    g(this, "iHash");
    g(this, "blockLen");
    g(this, "outputLen");
    g(this, "canXOF", !1);
    g(this, "finished", !1);
    g(this, "destroyed", !1);
    if (le(e), J(n, void 0, "key"), this.iHash = e.create(), typeof this.iHash.update != "function")
      throw new Error("expected Hash instance");
    this.blockLen = this.iHash.blockLen, this.outputLen = this.iHash.outputLen;
    const r = this.blockLen, o = new Uint8Array(r);
    o.set(n.length > r ? e.create().update(n).digest() : n);
    for (let i = 0; i < o.length; i++)
      o[i] ^= 54;
    this.iHash.update(o), this.oHash = e.create();
    for (let i = 0; i < o.length; i++)
      o[i] ^= 106;
    this.oHash.update(o), rt(o);
  }
  update(e) {
    return qt(this), this.iHash.update(e), this;
  }
  digestInto(e) {
    qt(this), nn(e, this), this.finished = !0;
    const n = e.subarray(0, this.outputLen);
    this.iHash.digestInto(n), this.oHash.update(n), this.oHash.digestInto(n), this.destroy();
  }
  digest() {
    const e = new Uint8Array(this.oHash.outputLen);
    return this.digestInto(e), e;
  }
  _cloneInto(e) {
    e || (e = Object.create(Object.getPrototypeOf(this), {}));
    const { oHash: n, iHash: r, finished: o, destroyed: i, blockLen: s, outputLen: c, canXOF: f } = this;
    return e = e, e.finished = o, e.destroyed = i, e.blockLen = s, e.outputLen = c, e.canXOF = f, e.oHash = n._cloneInto(e.oHash), e.iHash = r._cloneInto(e.iHash), e;
  }
  clone() {
    return this._cloneInto();
  }
  destroy() {
    this.destroyed = !0, this.oHash.destroy(), this.iHash.destroy();
  }
}
const vt = /* @__PURE__ */ (() => {
  const t = ((e, n, r) => new Ve(e, n).update(r).digest());
  return t.create = (e, n) => new Ve(e, n), t;
})(), ht = /* @__PURE__ */ Uint8Array.of(0), ur = /* @__PURE__ */ Uint8Array.of();
function dr(t, e, n, r = 32, o) {
  le(t), ft(r, "length"), J(e, void 0, "prk");
  const i = t.outputLen;
  if (e.length < i)
    throw new Error('"prk" must be at least HashLen octets');
  if (r > 255 * i)
    throw new Error("Length must be <= 255*HashLen");
  const s = Math.ceil(r / i);
  if (n === void 0 ? n = ur : J(n, void 0, "info"), !s)
    return o && rt(e), new Uint8Array();
  const c = o && s === 1 ? e : new Uint8Array(s * i), { iHash: f, oHash: a } = vt.create(t, e), u = o ? e : new Uint8Array(i), d = s > 1 ? (o == null ? void 0 : o.iHash) || t.create() : void 0;
  for (let h = 0; h < s - 1; h++) {
    ht[0] = h + 1;
    const w = f._cloneInto(d);
    h && w.update(u), w.update(n).update(ht).digestInto(u), a._cloneInto(d).update(u).digestInto(u), c.set(u, i * h);
  }
  if (ht[0] = s, s > 1 && f.update(u), f.update(n).update(ht).digestInto(u), a.update(u).digestInto(u), c.set(u, i * (s - 1)), f.destroy(), a.destroy(), d == null || d.destroy(), u !== c && rt(u), rt(ht), r === c.length)
    return c;
  const l = c.slice(0, r);
  return rt(c), l;
}
const lr = (t, e, n, r, o) => {
  le(t), n === void 0 && (n = new Uint8Array(t.outputLen));
  const i = vt.create(t, n).update(e);
  return dr(t, i.digest(), r, o, i);
}, tt = new TextEncoder(), On = new TextDecoder();
function K(t) {
  const e = document.querySelector(t);
  if (!e) throw new Error(`Air Handoff receiver is missing ${t}`);
  return e;
}
const hr = K("#pair-card"), pr = K("#receive-card"), gt = K("#pair-button"), gr = K("#forget-button"), _n = K("#device-name"), $t = K("#pair-error"), Ge = K("#receive-error"), Je = K("#connection-state"), An = K("#empty-state"), Tn = K("#transfer-list");
let P = yr(), fe = 0;
const dt = /* @__PURE__ */ new Set();
_n.value = navigator.userAgent.includes("Android") ? "Android phone" : navigator.userAgent.includes("iPhone") ? "iPhone" : "My phone";
function Mt(t) {
  let e = "";
  for (const n of t) e += String.fromCharCode(n);
  return btoa(e).replaceAll("+", "-").replaceAll("/", "_").replaceAll("=", "");
}
function W(t) {
  const e = t.replaceAll("-", "+").replaceAll("_", "/") + "=".repeat((4 - t.length % 4) % 4);
  return Uint8Array.from(atob(e), (n) => n.charCodeAt(0));
}
function wr(t, e) {
  if (t.length !== e.length) return !1;
  let n = 0;
  for (let r = 0; r < t.length; r += 1)
    n |= t[r] ^ e[r];
  return n === 0;
}
function yr() {
  try {
    const t = JSON.parse(localStorage.getItem("heliox_air_handoff_credential") || "null");
    if (t != null && t.device_id && (t != null && t.device_secret)) return t;
  } catch {
  }
  return null;
}
function br(t) {
  P = t, localStorage.setItem("heliox_air_handoff_credential", JSON.stringify(t));
}
function mr() {
  P = null, localStorage.removeItem("heliox_air_handoff_credential"), dt.clear(), Tn.replaceChildren(), xe();
}
async function Er() {
  $t.textContent = "";
  const e = new URLSearchParams(location.hash.slice(1)).get("pair");
  if (!e) {
    $t.textContent = "Open this page by scanning the current pairing QR in Heliox.";
    return;
  }
  const n = _n.value.trim();
  if (!n) {
    $t.textContent = "Enter a name for this phone.";
    return;
  }
  gt.disabled = !0, gt.textContent = "Establishing encrypted channel…";
  try {
    const r = W(e), o = Ke.keygen(), i = vt(wt, r, Ne(tt.encode("pair-v1:"), o.publicKey)), s = await fetch("/api/pair", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        device_name: n,
        client_public_key: Mt(o.publicKey),
        client_proof: Mt(i)
      })
    }), c = await s.json();
    if (!s.ok) throw new Error(c.error || "Pairing failed");
    const f = W(c.server_public_key), a = vt(
      wt,
      r,
      Ne(tt.encode("server-v1:"), f, o.publicKey)
    );
    if (!wr(a, W(c.server_proof)))
      throw new Error("The computer could not be authenticated");
    const u = Ke.getSharedSecret(o.secretKey, f), d = lr(wt, u, r, tt.encode("heliox-air-handoff-pair-v1"), 32), l = de(d, W(c.nonce), tt.encode("heliox-air-handoff-credential-v1")).decrypt(
      W(c.credential)
    );
    br(JSON.parse(On.decode(l))), history.replaceState(null, "", location.pathname), xe(), await Ee();
  } catch (r) {
    $t.textContent = r instanceof Error ? r.message : "Pairing failed";
  } finally {
    gt.disabled = !1, gt.textContent = "Pair securely";
  }
}
async function me(t, e = {}) {
  if (!P) throw new Error("This phone is not paired");
  const n = (e.method || "GET").toUpperCase(), r = typeof e.body == "string" ? tt.encode(e.body) : new Uint8Array(), o = String(Date.now() / 1e3), i = Mt(Pn(18)), s = tt.encode([n, t, o, i, jt(wt(r))].join(`
`)), c = vt(wt, W(P.device_secret), s);
  return fetch(t, {
    ...e,
    headers: {
      ...e.headers || {},
      "X-Heliox-Device": P.device_id,
      "X-Heliox-Time": o,
      "X-Heliox-Nonce": i,
      "X-Heliox-Signature": Mt(c)
    }
  });
}
function xr(t, e) {
  if (!P) throw new Error("This phone is not paired");
  const n = de(W(P.device_secret), W(t.nonce), tt.encode(e)).decrypt(
    W(t.ciphertext)
  );
  return JSON.parse(On.decode(n));
}
async function Ee() {
  if (P)
    try {
      const t = await me("/api/pending"), e = await t.json();
      if (!t.ok) throw new Error(e.error || "Receiver authentication failed");
      const n = xr(e, "pending-v1");
      Ge.textContent = "";
      for (const r of n)
        dt.has(r.transfer_id) || await Br(r);
      An.classList.toggle("hidden", dt.size > 0);
    } catch (t) {
      Ge.textContent = t instanceof Error ? t.message : "Could not reach Heliox";
    } finally {
      clearTimeout(fe), P && (fe = window.setTimeout(Ee, 1800));
    }
}
async function Br(t) {
  if (!P) throw new Error("This phone is not paired");
  const e = `/api/transfers/${encodeURIComponent(t.transfer_id)}`, n = await me(e);
  if (!n.ok) {
    const c = await n.json();
    throw new Error(c.error || "Could not download the handoff");
  }
  const r = new Uint8Array(await n.arrayBuffer());
  if (r.length < 29) throw new Error("The encrypted handoff is incomplete");
  const o = de(
    W(P.device_secret),
    r.slice(0, 12),
    tt.encode(`transfer-v1:${t.transfer_id}`)
  ).decrypt(r.slice(12)), i = new Blob([new Uint8Array(o)], { type: t.mime_type }), s = URL.createObjectURL(i);
  Rr(t, s), dt.add(t.transfer_id);
}
function Rr(t, e) {
  const n = document.createElement("article");
  if (n.className = "transfer", t.mime_type.startsWith("image/")) {
    const a = document.createElement("img");
    a.src = e, a.alt = t.filename, n.append(a);
  }
  const r = document.createElement("div");
  r.className = "transfer-info";
  const o = document.createElement("strong");
  o.textContent = t.filename;
  const i = document.createElement("span");
  i.textContent = `${t.kind} · ${vr(t.size)}`;
  const s = document.createElement("div");
  s.className = "transfer-actions";
  const c = document.createElement("a");
  c.href = e, c.download = t.filename, c.textContent = "Save";
  const f = document.createElement("button");
  f.type = "button", f.textContent = "Received", f.addEventListener("click", async () => {
    const a = `/api/transfers/${encodeURIComponent(t.transfer_id)}/ack`;
    (await me(a, {
      method: "POST",
      body: "{}",
      headers: { "Content-Type": "application/json" }
    })).ok && (n.remove(), URL.revokeObjectURL(e), dt.delete(t.transfer_id), An.classList.toggle("hidden", dt.size > 0));
  }), s.append(c, f), r.append(o, i, s), n.append(r), Tn.prepend(n);
}
function vr(t) {
  return t < 1024 ? `${t} B` : t < 1024 * 1024 ? `${(t / 1024).toFixed(1)} KB` : `${(t / (1024 * 1024)).toFixed(1)} MB`;
}
function xe() {
  const t = !!P;
  hr.classList.toggle("hidden", t), pr.classList.toggle("hidden", !t), Je.classList.toggle("online", t), Je.textContent = t ? "Paired · encrypted" : "Not paired", clearTimeout(fe), t && Ee();
}
gt.addEventListener("click", () => void Er());
gr.addEventListener("click", mr);
xe();
