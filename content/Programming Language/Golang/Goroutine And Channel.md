사람들이 go를 쓰는 이유에는 여러가지가 있을 것이다.

1. 컴파일 언어라서 안전성이 높다.
2. 바이너리 파일로 크로스 컴파일이 가능하다.
3. 디컴파일이 가능하긴 하나 원본 코드 상태로는 불가능해서 나름의 코드 보안성도 챙길 수 있다.
4. 컴파일 언어지만 컴파일 속도가 상당히 빠르며 문법 또한 타입 추론을 지원하는 등 다른 컴파일 언어에 비해 유동적이여서 인터프리터 언어로 작업하는 것 만큼의 생산성이 나온다.
5. 병행 프로그래밍에 유용하다.

>한마디로 여러 의미로 쉽고 빠르다.

이번 포스팅에서는 병행 프로그래밍에 유용하다라는 말에 대해서 알아볼 것이다.

## Goroutine

goroutine은 많은 사람들이 go를 쓰는 이유 중 하나이지 않을까 싶다.

우선 아래의 코드를 보자.
```go
package main  
  
import (  
	"fmt"  
	"time"  
)  
  
func main() {  
	task1()  
	task2()  
}  
  
func task1() {  
	arr := [4]int{1, 2, 3, 4}  
	for _, elm := range arr {  
		time.Sleep(time.Second)  
		fmt.Println(elm)  
	}  
}  
  
func task2() {  
	arr := [4]int{5, 6, 7, 8}  
	for _, elm := range arr {  
		time.Sleep(time.Second)  
		fmt.Println(elm)  
	}  
}
```

위 코드의 실행 시간은 8초 정도가 걸리며 1, 2, 3, 4, 5, 6, 7, 8 이렇게 출력될 것이다.
이게 탑 다운 형식으로 진행되는 일반적인 프로그래밍 형태이다.

goroutines은 작업을 병렬로 처리할 수 있게 해준다.
task1 함수와 task2 함수를 동시에 실행할 수 있는 것이다.
그리고 그 방법은 매우 간단하다.
```go
package main  
  
import (  
	"fmt"  
	"time"  
)  
  
func main() {  
	go task1()  
	task2()  
}  
  
func task1() {  
	arr := [4]int{1, 2, 3, 4}  
	for _, elm := range arr {  
		time.Sleep(time.Second)  
		fmt.Println(elm)  
	}  
}  
  
func task2() {  
	arr := [4]int{5, 6, 7, 8}  
	for _, elm := range arr {  
		time.Sleep(time.Second)  
		fmt.Println(elm)  
	}  
}
```

실행 시키고 다음줄로 넘어가고 싶은 함수 앞에 go 키워드를 작성하면 끝이다.
그러면 두 함수를 거의 동시에 실행 했기 때문에 실행 시간은 4초 정도 걸리고 출력 값도 1, 2, 3, 4, 5, 6, 7, 8 이렇게 출력되지 않고 1, 5, 6, 2, 3, 7, 8 이렇게 출력될 것이다.

출력 값 중 4가 없는데 빼먹은게 아니라 정말 저런식으로 출력 되는 경우가 있다.
task2에도 go 키워드를 붙히고 실행 시켜보자.
```go
func main() {  
	go task1()  
	go task2()  
}
```
아마 그냥 프로그램이 종료될 것이다.

이건 오류 같은 것이 아니라 Goroutine의 특성이다.
Goroutine은 오직 프로그램이 작동하는 동안, 즉 main 함수가 실행 되는 동안에만 유효하다. 

go가 task1을 실행하고 task2를 실행하고 main 함수가 더 이상 진행할 작업이 없기 때문에 바로 종료 되며 main의 작업이 종료되었기에 goroutine 또한 전부 종료되는 것이다.

아까 4가 출력되지 않은 이유도 goroutine이 실행 중인 task1 함수에서 4가 출력되기 전에 main에서의 task2 작업이 먼저 끝났고 main이 종료되면서 goroutine이 종료 되었던 것이다.

>다시 한번 강조하지만 main 함수는 goroutine을 기다려주지 않는다.

위 설명이 이게 무슨 소리지 싶다면 **비동기 프로그래밍**이라는 주제로 공부를 하기바란다.

좀 더 자세히 goroutine 개념에 대해 공부하고 싶다면 아래 글을 읽어보자.
- http://golang.site/go/article/21-Go-%EB%A3%A8%ED%8B%B4-goroutine#google_vignette


그럼 main이 goroutine의 작업 상태를 확인할 수 있는 방법은 없는 것일까?
goroutine이랑 main 함수 사이에 정보를 주고 받는 **channel**이라는 개념이 있다.

## Channel

가볍게 알아봤을 때는 일종의 작업 큐(Queue) 느낌이다.

```go
package main  
  
import (  
	"fmt"  
	"time"  
)  
  
func main() {  
	c := make(chan int)  
	// channel 생성 방법, make 함수를 사용하며 전달할 정보의 타입을 지정해야한다.  
	go task1(c)  
	// goroutine 실행 시 채널을 함수의 인자로 전달  
	go task2(c)  
	result1 := <-c  
	// 작업의 결과를 받는 방법.  
	// 작업의 결과를 기다리는 것과도 같은 의미다.  
	fmt.Println(result1)  
	result2 := <-c  
	fmt.Println(result2)  
}  
  
func task1(c chan int) {  
	sum := 0  
	arr := [4]int{1, 2, 3, 4}  
	for _, elm := range arr {  
		time.Sleep(time.Second)  
		sum += elm  
	}  
	c <- sum  
	// 전달 받은 채널로 결과를 전달  
}  
  
func task2(c chan int) {  
	sum := 0  
	arr := [4]int{5, 6, 7, 8}  
	for _, elm := range arr {  
		time.Sleep(time.Second)  
		sum += elm  
	}  
	c <- sum  
}
```

멀티프로세싱이나 하위 프로세스를 만들 때 데이터 전달 시 사용되는 pipe와 비슷한 형식이다.

goroutine으로 작업할 함수를 호출할 때 데이터를 받아야 한다면 함수의 인자로 채널을 넘겨준다.
그리고 위 코드에서 보면 알 수 있듯이 <- 연산자를 통해 데이터를 전달한다.
>주의할 점은 채널을 통해 전달하려는 값의 타입을 지정해야한다.

다만 이 채널은 goroutine을 호출한 순서대로 작업의 결과 값을 저장하지 않는다. 먼저 끝난 작업의 결과가 채널이라는 Queue로 들어가고 값을 받을 때도 먼저 끝난 작업의 결과가 나온다고 볼 수 있다.

그런데 위 형식의 코드는 goroutine을 여러번 사용하면 사용한 만큼 채널에서 값을 받는 코드를 작성해야 한다. 아래 예시 처럼 말이다.

```go
// main만 작성

func main() {  
	c := make(chan int)  
	go task1(c)
	go task1(c)
	go task1(c)  
	go task2(c)
	go task2(c)
	go task2(c)  
	result1 := <-c
	result2 := <-c  
	result3 := <-c
	result4 := <-c
	result5 := <-c
	result6 := <-c
	// ... result 사용 생략
}  

```

이를 간단하게 하기 위해 반복문으로 goroutine을 기다릴 수 있다.

```go
package main  
  
import (  
	"fmt"  
	"time"  
)  
  
func main() {  
	c := make(chan int)  
	arr := [5][3]int{  
		{1, 2, 3},  
		{4, 5, 6},  
		{7, 8, 9},  
		{10, 11, 12},  
		{13, 14, 15},  
	}  
	  
	for _, elm := range arr {  
		go sumArray(c, elm)  
	}  
	  
	for i := 0; i < len(arr); i++ {  
		fmt.Println(<-c)  
	}  
}  
	  
func sumArray(c chan int, arr [3]int) {  
	sum := 0  
	for _, elm := range arr {  
	time.Sleep(time.Second)  
	sum += elm  
	}  
	c <- sum  
}
```

python의 async, await나 다른 프로그래밍 언어의 비동기 프로그래밍 방식을 사용해봤다면
어떤 방식으로 사용되는지 코드를 보면 이해할 수 있을 것이다.

위는 단순히 배열의 합을 구하는 함수로 예시를 들었지만 이에 국한되는 것이 아니라 비동기로 처리해야할 일련의 작업들을 배열에 담고 비동기로 실행시킨 뒤 작업이 담긴 배열(arr)의 길이만큼 반복문으로 채널의 결과 값을 기다린다.

작업을 한번씩 호출하고 결과도 한번씩 받는 것 보다 깔끔하게 작성 가능하다.
