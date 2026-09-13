"""외부 출처 다운로드용 URL, DNS, redirect 안전 경계."""
from __future__ import annotations

import ipaddress
import socket
import unicodedata
import urllib.parse
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Callable, Iterator, Sequence

import httpx


REDIRECT_STATUSES = {301, 302, 303, 307, 308}


class UnsafeURL(ValueError):
    """URL이 허용된 외부 HTTP 목적지로 검증되지 않았을 때."""


@dataclass(frozen=True)
class ValidatedURL:
    url: str
    host: str
    addresses: tuple[str, ...]
    private_allowed: bool


def _host_key(host: str) -> str:
    return host.strip().lower().rstrip(".").removeprefix("[").removesuffix("]")


def _ip(value: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address:
    try:
        return ipaddress.ip_address(value.split("%", 1)[0])
    except ValueError as error:
        raise UnsafeURL("DNS가 유효하지 않은 IP 주소를 반환했습니다") from error


def validate_url(url: str, allow_private_hosts: Sequence[str] = (),
                 resolver: Callable | None = None) -> ValidatedURL:
    """HTTP(S) URL과 해당 시점의 모든 DNS 답변을 검증한다.

    사설 주소는 호스트 이름이 ``allow_private_hosts``에 정확히 명시된 경우에만
    허용한다. 여러 DNS 답변 중 하나라도 공용 경로가 아니면 전체 URL을 거부한다.
    """
    if not isinstance(url, str) or not url or any(unicodedata.category(char) == "Cc" for char in url):
        raise UnsafeURL("URL이 비어 있거나 제어 문자를 포함합니다")
    try:
        parsed = urllib.parse.urlsplit(url)
        port = parsed.port
        host = parsed.hostname
    except ValueError as error:
        raise UnsafeURL("URL 형식이 올바르지 않습니다") from error
    if parsed.scheme.lower() not in {"http", "https"}:
        raise UnsafeURL("http 또는 https URL만 가져올 수 있습니다")
    if parsed.username is not None or parsed.password is not None:
        raise UnsafeURL("인증정보가 포함된 URL은 가져올 수 없습니다")
    if not host:
        raise UnsafeURL("URL에 호스트 이름이 없습니다")

    host_key = _host_key(host)
    allowed = host_key in {_host_key(item) for item in allow_private_hosts if isinstance(item, str)}
    service_port = port or (443 if parsed.scheme.lower() == "https" else 80)
    try:
        literal = ipaddress.ip_address(host_key.split("%", 1)[0])
    except ValueError:
        resolve = resolver or socket.getaddrinfo
        try:
            answers = resolve(host, service_port, type=socket.SOCK_STREAM)
        except (OSError, UnicodeError) as error:
            raise UnsafeURL("호스트의 DNS 주소를 확인할 수 없습니다") from error
        addresses = tuple(sorted({_ip(answer[4][0]).compressed for answer in answers if len(answer) >= 5 and answer[4]}))
        if not addresses:
            raise UnsafeURL("호스트의 DNS 주소를 확인할 수 없습니다")
    else:
        addresses = (literal.compressed,)

    if not allowed and any(not _ip(address).is_global for address in addresses):
        raise UnsafeURL("공용 인터넷 주소가 아닌 목적지는 허용되지 않습니다")
    return ValidatedURL(url=url, host=host_key, addresses=addresses, private_allowed=allowed)


def _connected_peer(response: httpx.Response) -> str | None:
    """httpx가 노출하는 경우 실제 연결 상대 IP를 반환한다."""
    stream = response.extensions.get("network_stream")
    if stream is None:
        return None
    try:
        address = stream.get_extra_info("server_addr")
    except (AttributeError, OSError):
        address = None
    if not address:
        try:
            sock = stream.get_extra_info("socket")
            address = sock.getpeername() if sock is not None else None
        except (AttributeError, OSError):
            address = None
    if isinstance(address, (tuple, list)) and address:
        return str(address[0])
    return str(address) if address else None


def _validate_connected_peer(response: httpx.Response, target: ValidatedURL) -> None:
    """확인 가능한 실제 peer가 검증 DNS 답변과 다른 경우 연결을 막는다."""
    peer = _connected_peer(response)
    if not peer:
        return
    peer_ip = _ip(peer)
    if peer_ip.compressed not in target.addresses:
        raise UnsafeURL("연결된 서버가 검증한 DNS 주소와 다릅니다")
    if not target.private_allowed and not peer_ip.is_global:
        raise UnsafeURL("연결된 서버가 공용 인터넷 주소가 아닙니다")


@contextmanager
def open_safe_stream(client: httpx.Client, url: str, *, allow_private_hosts: Sequence[str] = (),
                     max_redirects: int = 5, resolver: Callable | None = None) -> Iterator[httpx.Response]:
    """각 이동 목적지를 재검증하며 최종 GET 응답 stream을 연다.

    DNS 사전검사와, transport가 peer 정보를 제공할 때의 연결 후 검사를 함께 쓴다.
    HTTP transport가 peer 정보를 노출하지 않는 환경의 DNS 재결합 경쟁까지 완전히
    제거하는 연결 고정 API는 아니다.
    """
    if max_redirects < 0:
        raise ValueError("max_redirects는 0 이상이어야 합니다")
    current = url
    for redirect_count in range(max_redirects + 1):
        target = validate_url(current, allow_private_hosts, resolver)
        with client.stream("GET", current) as response:
            _validate_connected_peer(response, target)
            location = response.headers.get("location")
            if response.status_code not in REDIRECT_STATUSES or not location:
                yield response
                return
            if redirect_count >= max_redirects:
                raise UnsafeURL(f"redirect가 {max_redirects}회를 초과했습니다")
            current = urllib.parse.urljoin(str(response.url), location)
    raise UnsafeURL(f"redirect가 {max_redirects}회를 초과했습니다")


__all__ = ["UnsafeURL", "ValidatedURL", "open_safe_stream", "validate_url"]
