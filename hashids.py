"""Implements the hashids algorithm in python. For more information, visit
http://www.hashids.org/. Compatible with Python 2.5--3"""
from __future__ import division
from itertools import chain
from math import ceil
import re

__version__ = '0.8.3'

RATIO_ALPHABET_SEPARATORS = 3.5
RATIO_ALPHABET_GUARDS = 12

# Python 2/3 compatibility code
try:
    _STR_TYPE = basestring
except NameError:
    _STR_TYPE = str

def _head(iterable):
    """Extracts the first value from an iterable."""
    # Python < 2.6 does not have `next()`
    # Python 3 does not have generator.next()
    for value in iterable:
        return value

# end of compatibility code

def _is_str(candidate):
    """Returns whether a value is a string."""
    return isinstance(candidate, _STR_TYPE)

def _is_uint(number):
    """Returns whether a value is an unsigned integer."""
    try:
        return number == int(number) and number >= 0
    except ValueError:
        return False

def _replace_index(list_object, index, value):
    """Replaces a value in a list_object with another value. Returns the
    replaced value."""
    list_object.insert(index, value)
    return list_object.pop(index + 1)

def _to_front(value, iterator):
    """Yields `value`, then all other elements from `iterator` if they are not
    equal to `value`."""
    return chain((value,), (x for x in iterator if x != value))

def _hash(number, alphabet):
    """Hashes `number` using the given `alphabet` sequence."""
    hashed = ''
    len_alphabet = len(alphabet)
    while True:
        hashed = alphabet[number % len_alphabet] + hashed
        number //= len_alphabet
        if not number:
            return hashed

def _unhash(hashed, alphabet):
    """Restores a number tuple from hashed using the given `alphabet` index."""
    number = 0
    len_hash = len(hashed)
    len_alphabet = len(alphabet)
    for i, character in enumerate(hashed):
        position = alphabet.index(character)
        number += position * len_alphabet ** (len_hash - i - 1)

    return number

def _reorder(string, salt):
    """Reorders `string` according to `salt`."""
    len_salt = len(salt)

    if len_salt == 0:
        return string

    i, v, p = len(string) - 1, 0, 0
    while i > 0:
        v %= len_salt
        integer = ord(salt[v])
        p += integer
        j = (integer + v + p) % i

        temp = string[j]
        trailer = string[j+1:] if j + 1 < len(string) else ''
        string = string[0:j] + string[i] + trailer
        string = string[0:i] + temp + string[i+1:]

        i -= 1
        v += 1

    return string

def _index_from_ratio(dividend, divisor):
    return int(ceil(dividend / divisor))

def _re_class(characters):
    """Creates a regular expression with a character class matching
    all `characters`."""
    return re.compile('[%s]' % re.escape(''.join(characters)))

class Hashids(object):
    """Hashes and restores values using the "hashids" algorithm."""
    PRIMES = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43)

    def __init__(self, salt='', min_length=0,
                 alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890'):
        """
        Initializes a Hashids object with salt, minimum length, and alphabet.

        :param salt: A string influencing the generated hash ids.
        :param min_length: The minimum length for generated hashes
        :param alphabet: The characters to use for the generated hash ids.
        """
        self._min_length = max(int(min_length), 0)
        self._salt = salt

        separators = ''.join(x for x in 'cfhistuCFHISTU' if x in alphabet)
        alphabet = ''.join(x for i, x in enumerate(alphabet)
                           if alphabet.index(x) == i and x not in separators)

        len_alphabet, len_separators = len(alphabet), len(separators)
        if len_alphabet + len_separators < 16:
            raise ValueError('Alphabet must contain at least 16 '
                             'unique characters.')

        separators = _reorder(separators, salt)

        min_separators = _index_from_ratio(len_alphabet, RATIO_ALPHABET_SEPARATORS)
        if not separators or len_separators < min_separators:
            if min_separators == 1:
                min_separators = 2
            if min_separators > len_separators:
                split_at = min_separators - len_separators
                separators += alphabet[:split_at]
                alphabet = alphabet[split_at:]
                len_alphabet = len(alphabet)

        alphabet = _reorder(alphabet, salt)
        num_guards = _index_from_ratio(len_alphabet, RATIO_ALPHABET_GUARDS)
        if len_alphabet < 3:
            guards = separators[:num_guards]
            separators = separators[num_guards:]
        else:
            guards = alphabet[:num_guards]
            alphabet = alphabet[num_guards:]

        self._alphabet = alphabet
        self._guards = guards
        self._separators = separators

    def encrypt(self, *values):
        """Builds a hash from the passed `values`.

        :param values The values to transform into a hashid

        >>> hashids = Hashids('arbitrary salt', 16, 'abcdefghijkl')
        >>> hashids.encrypt(1, 23, 456)
        'fhblhkfjejddjbdl'
        """
        if not (values and all(_is_uint(x) for x in values)):
            return ''

        return self._encode(values)

    def _encode(self, values):
        """Helper method that does the hash building without argument checks."""

        alphabet = self._alphabet
        separators = self._separators
        salt = self._salt
        min_length = self._min_length

        len_values = len(values)
        len_alphabet = len(alphabet)
        len_separators = len(separators)
        values_hash = sum(x % (i + 100) for i, x in enumerate(values))
        encoded = lottery = alphabet[values_hash % len(alphabet)]

        last = None
        for i, value in enumerate(values):
            alphabet_salt = (lottery + salt + alphabet)[:len_alphabet]
            alphabet = _reorder(alphabet, alphabet_salt)
            last = _hash(value, alphabet)
            encoded += last

            if i < len_values - 1:
                value %= ord(last[0]) + i
                encoded += separators[value % len_separators]

        guards = self._guards
        len_guards = len(guards)
        if len(encoded) < min_length:
            guard_index = (values_hash + ord(encoded[0])) % len_guards
            encoded = guards[guard_index] + encoded

            if len(encoded) < min_length:
                guard_index = (values_hash + ord(encoded[2])) % len_guards
                encoded += guards[guard_index]

        split_at = len_alphabet // 2
        while len(encoded) < min_length:
            alphabet = _reorder(alphabet, alphabet)
            encoded = alphabet[split_at:] + encoded + alphabet[:split_at]
            excess = len(encoded) - min_length
            if excess > 0:
                from_index = excess // 2
                encoded = encoded[from_index:from_index+min_length]

        return encoded

    def _ensure_length(self, hashid, values, alphabet):
        """Helper method that extends a hashid if it does not have the
        minimum lenght."""
        length = self._min_length
        salt = self._salt
        len_hashed = len(hashid)
        if len_hashed < length:
            first_index = sum((i + 1) * value for i, value in enumerate(values))

            guards = self._guards
            len_guards = len(guards)
            guard_index = first_index % len_guards
            hashid = guards[guard_index] + hashid
            len_hashed += 1

            if len_hashed < length:
                hashid += guards[(guard_index + len_hashed) % len_guards]
                len_hashed += 1

        while len_hashed < length:
            pad = ord(alphabet[1]), ord(alphabet[0])
            pad_left = self._encode(pad, alphabet, salt)[0]
            pad_right = self._encode(pad, alphabet, '%d%d' % pad)[0]
            hashid = pad_left + hashid + pad_right

            len_hashed = len(hashid)
            excess = len_hashed - length
            if excess > 0:
                hashid = hashid[excess//2:-excess//2]

            alphabet = list(_reorder(alphabet, salt + hashid))

        return hashid

    def decrypt(self, hashid):
        """Restore a tuple of numbers from the passed `hashid`.

        :param hashid The hashid to decrypt

        >>> hashids = Hashids('arbitrary salt', 16, 'abcdefghijkl')
        >>> hashids.decrypt('fhblhkfjejddjbdl')
        (1, 23, 456)
        """
        if not hashid or not _is_str(hashid):
            return ()
        try:
            return tuple(self._decode(hashid))
        except:
            return ()

    def _decode(self, hashid):
        """Helper method that restores the values encoded in a hashid without
        argument checks."""
        parts = self._guards_re.split(hashid)
        hashid = parts[1] if 2 <= len(parts) <= 3 else parts[0]

        lottery_char = None
        hash_parts = self._separators_re.split(hashid)
        for part in ((i, x) for i, x in enumerate(hash_parts) if x):
            i, sub_hash = part
            if i == 0:
                lottery_char = hashid[0]
                sub_hash = sub_hash[1:]
                alphabet = _to_front(lottery_char, self._alphabet)

            if lottery_char and alphabet:
                salt = '%d%s' % (ord(lottery_char) & 12345, self._salt)
                alphabet = list(_reorder(alphabet, salt))
                yield _unhash(sub_hash, alphabet)
