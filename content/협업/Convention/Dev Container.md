
# 참고자료
>[!Info]
>https://code.visualstudio.com/docs/devcontainers/containers
>https://learn.microsoft.com/ko-kr/training/modules/use-docker-container-dev-env-vs-code/

---
# Dev Container란?

DevContainer(Development Container)는 **컨테이너 기반의 완전한 개발 환경**을 제공하는 기술이다. 개발에 필요한 모든 도구가 담긴 "이사 갈 수 있는 사무실"과도 같다.

일반적으로 새 프로젝트를 시작하면 다음과 같은 과정을 거친다
- Python 버전 맞추기
- Node.js 설치하기
- 데이터베이스 설정하기
- 각종 라이브러리 의존성 설치하기

DevContainer는 이 모든 과정을 **설정 파일 하나로 자동화**한다.

---
# Dev Container의 장점

1. 환경 설정의 일관성
   "내 컴퓨터에서는 되는데요?"를 차단한다. 모든 팀원이 동일한 환경에서 작업하므로 환경 차이로 인한 버그가 사라진다.
   
2. 빠른 온보딩
   신입 개발자나 새로운 팀원이 합류했을 때, 복잡한 설정 문서를 따라갈 필요 없이 몇 번의 클릭으로 개발 환경이 준비된다.
   
3. 호스트 시스템 보호
   개발 도구와 의존성이 모두 컨테이너 안에 설치되므로, 로컬 컴퓨터는 깨끗하게 유지된다.
   
4. 프로젝트별 독립 환경
   프로젝트 A는 Python 3.9, 프로젝트 B는 Python 3.11을 사용해도 각 프로젝트가 독립된 컨테이너에서 실행되므로 문제가 없다.
   
5. 재현 가능한 개발 환경
   1년 후에 프로젝트를 다시 열어도 정확히 같은 환경에서 작업할 수 있습니다.

---
# Visual Studio Code에서 Dev Container 시작하기

### 사전 준비사항

다음 두 가지가 설치되어 있어야 한다.

- **Docker Desktop** (Windows/Mac) 또는 **Docker Engine** (Linux)
- **Visual Studio Code**

### 1. 확장 프로그램 설치
VSCode에서 Microsoft의 "Dev Containers" 확장 프로그램을 설치.

### 2. Dev Container 설정 파일 만들기

devcontainer.json 파일 작성 예시
```json
{
	"name": "컨테이너 이름",
	
	// Dockerfile 기반 빌드 설정
    "build": {
        // Dockerfile 경로
        "dockerfile": "Dockerfile",
        // 빌드 컨텍스트 (프로젝트 루트)
        "context": "..",
        // 빌드 인자
        "args": {
            "USERNAME": "vscode",
            "USER_UID": "1000",
            "USER_GID": "1000"
        }
    },
    // 컨테이너 실행 시 사용자
    "remoteUser": "vscode",
    // 호스트와 공유할 볼륨 마운트, 필요한 파일 옮기는 작업
    "mounts": [],

    // 컨테이너 생성 후 실행할 명령어
    "postCreateCommand": "bash .devcontainer/post-create.sh",
    // 포트 포워딩 설정
    "forwardPorts": [
        8000  // FastAPI 기본 포트
    ],

    // 포트별 레이블 설정 (VSCode UI에 표시)
    "portsAttributes": {
        "8000": {
            "label": "FastAPI Application",
            "onAutoForward": "notify"
        }
    },
    // VSCode 설정 커스터마이징
    // https://containers.dev/supporting 고
    "customizations": {
	    "vscode": {
		    // 자동 설치한 확장 프로그램
		    "extensions": [],
		    // VSCode 설정
		    "settings": {
		    }
	    }
    },
    // 컨테이너 기능 추가
    // https://containers.dev/features 참고
    "features": {
    },
    // 환경 변수 설정
    "remoteEnv": {
		"PYTHONPATH": "/workspace",
		"ENVIRONMENT": "development"
    },
    // 컨테이너 실행 옵션
    "runArgs": [
		// 컨테이너 이름
		"--name=fastapi-devcontainer",
		// 호스트 네트워크 모드 (선택사항, 포트 충돌 주의)
		// "--network=host"
    ],
    // 호스트 요구사항
    "hostRequirements": {
		"cpus": 2,
		"memory": "4gb",
		"storage": "32gb"
    }
}
```

공식 문서의 옵션에 대한 설명

| 옵션                  | 설명                                                                                                                                                                                                                                                                                 |
| ------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `image`             | VS Code에서 개발을 하는 데 필요한 컨테이너 터미널( [Docker Hub](https://hub.docker.com/) , [GitHub Container Registry](https://docs.github.com/packages/guides/about-github-container-registry) , [Azure Container Registry](https://azure.microsoft.com/services/container-registry/) )의 이미지 이름입니다. |
| `dockerfile`        | `image`를 사용하는 대신 `image`로 사용하려는 `Dockerfile`의 상대 경로를 `dockerfile` 속성으로 사용할 수 있습니다.                                                                                                                                                                                                 |
| `features`          | 추가할 [Dev Container 기능](https://code.visualstudio.com/docs/devcontainers/containers#_dev-container-features) ID 및 관련 옵션을 제공합니다.                                                                                                                                                     |
| `customizations`    | VS Code의 속성 `settings`과 동일한 도구별 속성을 구성합니다.`extensions`                                                                                                                                                                                                                             |
| `settings`          | `settings.json`컨테이너/머신별 설정 파일(예: )에 대해 추가합니다 `"terminal.integrated.defaultProfile.linux": "bash"`.                                                                                                                                                                                 |
| `extensions`        | 컨테이너가 생성될 때 컨테이너 내부에 설치해야 하는 확장 프로그램을 호스팅하는 확장 프로그램 ID 배열입니다.                                                                                                                                                                                                                      |
| `forwardPorts`      | 내부에서 사용할 수 있는 포트 목록을 작성합니다.                                                                                                                                                                                                                                                        |
| `portsAttributes`   | 특정 전달 포트에 대한 기본 속성을 설정합니다.                                                                                                                                                                                                                                                         |
| `postCreateCommand` | 콘솔이 생성된 후 콘솔 게임 또는 콘솔 목록입니다.                                                                                                                                                                                                                                                       |
| `remoteUser`        | VS Code 컨테이너에서 실행하는 사용자(하위 프로세스 포함)를 재정의합니다. 그건 .입니다 `containerUser`.                                                                                                                                                                                                              |
본인의 상황에 맞게 공식 문서를 참고하여 파일을 작성한 뒤 프로젝트 루트에 .devcontainer 폴더를 생성한 뒤 devcontainer.json 파일을 만든다.

그리고 Ctrl + Shift + P 입력 후 Dev containers: Rebuild Without Cache and Reopen in Container 검색하여 실행한다.

dockerfile 옵션을 통해 기존에 생성한 Dockerfile 기반으로 컨테이너를 만들거나 docker-compose.yml 파일 활용 등 여러 방식이 존재하고 활용 방법도 무궁무진 해보인다. 대신 그 만큼 설정 옵션들 또한 어마어마하게 많았다. (위의 표가 다가 아님.)

> [!info]
> 파일 작성이 어렵다면 Ctrl + Shift + P를 입력한 뒤 Dev Containers: Add Dev Container Configuration Files를 검색 하여 가이드에 따라 개발 환경을 선택한 뒤 자동으로 작성되는 파일들로 시작해도 된다.

---
# Dev Container의 작동 원리

단순히 컨테이너를 실행하는 것이 어떻게 개발 환경을 맞춰주는건가 싶어서 찾아봤는데 컨테이너가 하나의 VS Code의 서버가 되어주는 거였다. 모든 개발 환경 및 extensions를 포함한 VS Code 서버가 컨테이너로 실행되고 화면으로 보는 앱의 UI가 클라이언트가 되는 거였다.