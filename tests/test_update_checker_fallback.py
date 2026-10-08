from services.update_checker import UpdateChecker


class FakeResponse:
    def __init__(self, status_code, payload, reason="OK"):
        self.status_code = status_code
        self.reason = reason
        self._payload = payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self):
        self.urls = []

    def get(self, url, **kwargs):
        self.urls.append(url)
        if url.endswith("/releases/latest"):
            return FakeResponse(404, {"message": "Not Found"}, reason="Not Found")
        return FakeResponse(
            200,
            [
                {
                    "tag_name": "v0.1.1",
                    "name": "JARVIS v0.1.1 - update system test",
                    "draft": False,
                    "prerelease": False,
                    "html_url": "https://github.com/jelr1k/localjarvisgolos/releases/tag/v0.1.1",
                    "published_at": "2026-10-02T19:15:39Z",
                    "assets": [
                        {
                            "name": "jarvis.zip",
                            "browser_download_url": "https://github.com/jelr1k/localjarvisgolos/releases/download/v0.1.1/jarvis.zip",
                            "size": 174488,
                        }
                    ],
                }
            ],
        )


def test_update_checker_falls_back_to_release_list_after_latest_404():
    session = FakeSession()
    info = UpdateChecker(session=session).check("0.1.0")

    assert info.latest_version == "0.1.1"
    assert info.update_available is True
    assert info.tag_name == "v0.1.1"
    assert info.release_name == "JARVIS v0.1.1 - update system test"
    assert [asset.name for asset in info.assets] == ["jarvis.zip"]
    assert session.urls == [
        "https://api.github.com/repos/jelr1k/localjarvisgolos/releases/latest",
        "https://api.github.com/repos/jelr1k/localjarvisgolos/releases?per_page=20",
    ]


def test_update_checker_reports_no_release_when_fallback_list_is_empty():
    class EmptySession(FakeSession):
        def get(self, url, **kwargs):
            self.urls.append(url)
            if url.endswith("/releases/latest"):
                return FakeResponse(404, {"message": "Not Found"}, reason="Not Found")
            return FakeResponse(200, [])

    info = UpdateChecker(session=EmptySession()).check("0.1.0")

    assert info.latest_version == "0.1.0"
    assert info.update_available is False
    assert info.release_name == "Релизов пока нет"
