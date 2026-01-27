---
layout: single
title: "파일 검색기 만들기"
categories: Toy-Project
tag: 
sidebar:
    nav: "counts"
search: true
use_math: false
---
# 파일 검색기 만들기

### github 주소
https://github.com/YunKyungho/searchFile

## 만드는 계기

- 회사에서 Go를 쓰자는 말이 나와서 배웠는데 회사라 그런가 큰 변화가 없어서 자연스럽게 쓸 일도 사라졌다. 배운 거 까먹으면 아깝기도 해서 토이프로젝트를 만들기로 했다.
- 자사 솔루션의 파일 탐색 속도가 느린 것 같아서 개선도 하고 공부도 해볼겸 파일 시스템에 대해서 공부했는데 이 또한 쓸 일이 없게 됬다. 내 마음대로 중추가 될 수 있는 부분을 바꿀 순 없으니..
  내 마음대로 만들 수 있는 토이프로젝트라도 만들기로 했다.

그리고 파일 탐색 관련으로 조사하다가 알게된 오픈소스 프로젝트에서 영감을 받은 것도 있다.

## 참고한 오픈소스

https://github.com/t9t/gomft
NTFS(윈도우의 파일시스템)에서 MFT(master file table)를 볼륨 위치를 계산해서 찾고
이를 복사하여 파일을 분석하는 방식의 프로젝트.

MFT에 꽂혔던 이유는 everything이라는 windows 전용 파일 검색기가 MFT를 통하여 파일 인덱스를 만들고 메모리에 실어 빠른 검색속도를 만든다고 해서 이를 모방하려고 했었다. 그런데 결국 관리자 권한이 있어야만 가능한 로직이라 회사 솔루션에는 못쓸게 뻔해서 넘어갔다.

https://github.com/cboxdoerfer/fsearch
내가 모방할 프로젝트는 위의 fsearch 프로젝트다. (물론 GUI까지는 안 할 거다.)
이 프로젝트는 제작자가 windows에는 everything이 있는데 linux에는 가볍고 빠른 검색을 지원하는 툴이 없어서 직접 만들었다고한다.

코드를 읽어보니 대략 C언어 기본 함수 opendir을 통해 재귀함수로 모든 파일과 디렉토리를 탐색하고 sqlite로 데이터를 관리하는 방식이었다. 이후에 GUI와 다양한 검색 방식(정규식, 와일드 카드 등)을 지원하는 내용은 굳이 알아보지 않았다.


## 개발 과정

Go에 기본 모듈 중 재귀적으로 파일 탐색을 하는 함수가 있었다.
```go
package main

import (
	"fmt"
	"path/filepath"
)

func main () {
	err := filepath.WorkDir("탐색 시작 경로", 탐색 시 수행할 함수)
	if err != nil {
		fmt.Printf("Error: %v\n", err)
		return
	}
}
```

위 같은 형식으로 WorkDir 함수를 사용하면 된다.
원래는 탐색한 결과로 효율적인 파일 인덱스를 만들고 메모리에 실어서 검색 결과를 출력하는 형식으로 만들려고 했는데 내 컴퓨터(325GB 사용 중인 SSD) 기준 메모리를 1.5GB나 먹는다.

그래서 탐색 하자마자 sqlite DB에 저장하고 검색 시 메모리가 아니라 DB에서 가져오는 방식으로 만들어야겠다 생각하고 go-sqlite3라는 모듈의 사용법을 알아봤다.
```go
package pkg  
  
import (  
	"database/sql"  
	"log"  
  
	_ "github.com/mattn/go-sqlite3"  
)  
  
type Database struct {  
	handler *sql.DB  
}  
  
// NewDatabase is Constructor that open DB
func NewDatabase(dbFile string) *Database {  
	handler, err := sql.Open("sqlite3", dbFile)  
	if err != nil {  
		log.Fatalln(err)  
	}  
	db := Database{handler: handler}  
	db.createTable()  
	return &db  
}  
  
// CloseDatabase is close DB
func (d Database) CloseDatabase() {  
	d.handler.Close()  
}
```

이것도 크게 어려운점 없이 go-sqlite3 모듈을 설치만 하고 Go에서 기본 제공되는 database/sql 패키지로 연동이 가능하여 위 처럼 사용하면 된다. 또한 기본 sql 문법과 똑같아서 sql을 알면 크게 어려움이 없을 것이다.

cgo로 sqlite 로직까지 컴파일을 해버려서 프로그램이 실행되는 환경에 sqlite가 설치되어 있지 않아도 사용 가능하다. 이건 편하긴 하지만 테스트 과정에서 컴파일 시간이 너무 오래 걸린다는 단점도 있다.

아무튼 DB 작업 관련 함수도 구현하고 테스트를 해봤는데
![[images/searchFile/1.png]]
심상치 않은 디스크 활성시간률을 보인다. 수 많은 파일들을 하나 확인할 때 마다 IO 작업을 해서 이런 듯 하다. 검색해보니 디스크 활성시간이 100%에 도달하면 인터넷이 먹통되고 컴퓨터가 멈춘다는 말도 보여서 위험해 보였다. (메모리는 10GB를 쓰고 있으나 다른 프로세스들이고 테스트 시 사용된 메모리는 거의 없다시피 하다.)

파일 정보를 메모리에 특정 용량까지만 쌓아두다가 한번에 IO 작업을 하는 방식으로 바꿔야겠다.

```go

func checkMemUsage() bool {  
	m := runtime.MemStats{}  
	runtime.ReadMemStats(&m)  
	if m.Alloc/1024 > 51200 {  
		return true  
	}  
	return false  
}
```

위 처럼 runtime이라는 기본 모듈의 MemStats를 통해 현재 프로세스의 메모리 사용량 같은 정보를 확인할 수 있다. pprof라는 모듈로 좀 더 심화된 프로파일링도 가능하다고 하지만 너무 본격적이기는 싫었다. 어디까지나 Toy 프로젝트니..

디렉토리 탐색 과정에서 파일이 아닌 디렉토리를 만났을 때 위 함수를 실행하고 true일 경우 모아놓은 데이터는 전부 insert 하는 방식으로 만들었다.

속도는 당연히 IO 작업이 줄어 훨씬 빨라졌고 메모리도 1.5GB나 잡아먹을 일도 없다.
물론 디스크 활성시간률도 이상 없었다.

좀 놀라웠던 것은 내 컴퓨터에 104만개나 되는 파일이 있다는 것이다.
권한이 없는 디렉토리는 지나친 것이 이 정도였다.

