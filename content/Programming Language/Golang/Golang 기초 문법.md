
>설치 및 환경 설정은 공식 문서를 참고 바랍니다.
>https://go.dev/doc/

## Package

**디렉토리 구조**
```bash
learn-golang
└── basic
	├── mymod
	│	└── mymod.go
	└── main.go
```

go의 컴파일러는 패키지 이름이 main인 것을 먼저 찾는다.
따라서 컴파일을 위해 main package가 필수적이다.

```go
// main.go 파일 내용

package main
```

마찬가지로 main package를 찾은 뒤 내부의 main 함수를 찾아 실행시킨다.
(물론 컴파일이 아닌 공유 목적으로 만든 package라면 굳이 main이 있을 필요는 없다.)

```go
// main.go 파일 내용

package main

func main() {   

}
```


디렉토리 구조 참고 시 mymod 폴더 내부에 mymod.go가 존재하는데
```go
// mymod.go 파일 내용

package mymod
```
파일 내부에서 패키지명을 폴더명과 통일 시켜줘야 한다.
다만 파일명은 mymod.go가 아닌 무엇으로 해도 상관없다.

## Import

표준 라이브러리를 import 하는 것은 다른 언어와 같이 어렵지 않다.

```go
// main.go 파일 내용

package main

import "fmt"

func main() {   
	fmt.Println("Hello World")
}
```

다만 내가 만든 package를 import하고 함수를 호출하는 것은 좀 까다롭다.

예전 같은 경우 GOPATH(환경변수)/src 경로에 package를 추가하는 방식을 썼다고한다.
나는 비교적 최근에 생긴 mod를 추가하는 방법으로 진행할 것이다.

터미널을 열고 내 프로젝트의 루트 디렉토리(지금 나의 디렉토리 구조 상으로는 learn-golang)에서 다음 명령어를 실행한다.

```bash
go mod init github.com/YunKyungho/learn-golang
```

관용적으로 프로젝트명/디렉토리 구조 혹은 위 같이 github.com/username/repository  형식으로 명령어를 실행한다.

그러면 루트 디렉토리에 go.mod라는 파일이 생성되고 내용은 아래와 같이 작성된다.
```go
// go.mod 파일 내용

module github.com/YunKyungho/learn-golang  
  
go 1.20
```

>이게 무엇을 의미하는지는 나중에 알아보도록 하자.
>(golang 공식 문서 튜토리얼에서도 깊게 다루지 않는 내용이다.)
>https://go.dev/doc/tutorial/create-module

위 명령어를 실행한 뒤에 비로소 main.go 파일에서 아래와 같이 mymod package를 import 할 수 있다.
```go
// main.go 파일 내용

package main

import (  
	"fmt"  
	  
	"github.com/YunKyungho/learn-golang/basic/mymod"
)

func main() {   
	fmt.Println("Hello World")
}
```
여러 package를 import 할 때는 위 처럼 소괄호 안쪽에 엔터로 구분하여 작성한다.

## Variables and Constants

>문법, 키워드, 연산자, 타입 등을 자세히 확인하려면 아래 공식 문서를 참고하자.
>https://go.dev/ref/spec

상수와 변수의 선언 방법에 대해 알아보자.

```go
// main.go 파일 내용

package main

import "fmt"

func main() {
	const name string = "Kyungho"
	fmt.Println(name)
	
	var job string = "Develpoer"
	fmt.Println(job)
}
```

위가 기본적인 상수와 변수의 선언 방법이다.
(Go는 변수 선언 후 사용하지 않으면 에러 표시를 해줘서 Println을 사용했다.)

상수 - const
변수 - var
{const or var} {변수명} {type} = {value}
위 형식으로 선언이 가능하다.

재밌는 점은 Golang은 정적 타입 언어이지만 타입 추론이 가능하다는 것이다.
```go
// main.go 파일 내용

package main

import "fmt"

func main() {
	const name string = "Kyungho"
	fmt.Println(name)
	
	var job string = "Develpoer"
	fmt.Println(job)
	
	age := 28
	fmt.Println(age)
}
```

아래 추가된 내용 처럼 **:=** 대입 연산자를 통해 type 지정 없이 간단하게 변수 선언이 가능하며 이를 '타입 추론'이라고 한다.

>단 func 내부에서만 선언 가능하며 상수는 불가능하다.

그런데 **'저게 되면 동적 타입 언어가 아니냐?'** 할 수 있지만 **컴파일 시점**에 컴파일러가 **타입을 결정**하는 것이기에 실행 시점에 변수의 타입이 결정되는 python 같은 동적 타입 언어와는 엄연히 다르다. 

```go
// main() 함수 내부

age := 28
age = "28" // -> 오류 발생
```
그 예로 위 처럼 변수 선언 후 다른 타입의 값을 할당할 경우 오류가 발생한다.

## Function

go에서는 함수명의 첫 글자로 접근성을 제어한다.

```go
// mymod.go 파일 내용

package mymod  
  
import "fmt"  
  
// 소문자로 작성된 func은 private func이 되어 외부에서 호출할 수 없다.  
func sayBye() {  
	fmt.Println("Bye")  
}  
  
// 외부로 export를 위해선 대문자로 시작하는 func을 작성해야 한다.  
func SayHello() {  
	fmt.Println("Hello")  
}
```

이를 main.go에서 호출 해보자. 

```go
// main.go 파일 내용

package main

import (  
"fmt"  
  
"github.com/YunKyungho/learn-golang/basic/mymod"
)

func main() {   
	mymod.SayHello() // -> 정상 작동.
	mymod.sayBye() // -> 이 부분에서 에러 발생.
}
```

소문자로 시작하는 함수는 오직 동일 패키지 내부에서만 접근 가능하다.
재밌는 점은 다음 처럼 파일은 달라도 같은 패키지라면 private 함수도 호출이 가능하다는 것이다.

**디렉토리 구조**
```bash
learn-golang
└── basic
	├── mymod
	│	├── mymod.go
	│	└── modmod.go -> 신규 생성
	└── main.go
```

위 처럼 대충 아무 파일을 만들어 주고 (modmod.go) 아래 처럼 작성한 뒤에

```golang
// modmod.go 파일 내용

package mymod  
  
func UsingSayBye() {  
	sayBye()  
}
```

main.go에서 UsingSayBye 함수를 호출하면

```go
// main.go 파일 내용

package main

import (  
"fmt"  
  
"github.com/YunKyungho/learn-golang/basic/mymod"
)

func main() {   
	mymod.SayHello() // -> 정상 작동.
	mymod.UsingSayBye() // -> 정상 작동.
}
```

```bash
Hello
Bye
```
정상적으로 작동 한다.

위에서 작성한 함수들은 전부 입력 파라미터와 반환 값이 없었다.
다음은 함수에서 인자를 받는 방법이다.

```go
package main

import "fmt"

func main() {
	callFunctionWithParameter(3, 5)
}

func callFunctionWithParameter(a int, b int) {  
	fmt.Println(a + b)  
}

// 혹은 아래 처럼도 가능하다.

func callFunctionWithParameter(a, b int) { 
	// 인자 a와 b의 타입이 같은 경우 가장 뒤에 있는 인자의 타입만 명시해도 된다.
	fmt.Println(a + b)  
}

```

다음은 함수에서 값을 반환하는 방법이다.
(위에서 작성했던 함수들은 일종의 void 함수라고 볼 수 있겠다.)
```go
package main

import "fmt"

func main() {
	sum_value := callReturnFunction(3, 5)
	fmt.Println(sum_value)
	fmt.Println(callReturnFunction(5, 5))
}

func callReturnFunction(a, b int) int {  
	return a + b  
}

```

위 형식대로 함수 인자 옆에 반환 값의 타입을 명시 해줘야 한다.
그리고 이 반환 값은 main 함수에 있는 것 처럼 변수에 받아서 사용도 가능하고
변수에 대입하지 않고 바로 다른 함수 호출에 사용할 수도 있다.

여러 값을 동시에 반환 하는 함수를 작성할 수도 있다.
```go
package main

import "fmt"

func main() {
	length, upper_word := multipleReturnFunc("any word")  
	fmt.Println(length, upper_word)
}

func multipleReturnFunc(word string) (int, string) {  
	return len(word), strings.ToUpper(word)  
}
```

(몇개가 될지 모르는)여러 인자를 받는 함수를 작성할 수도 있다.
```go
package main

import "fmt"

func main() {
	manyParameterFunc("a", "b", "c", "d")
}

func manyParameterFunc(words ...string) {  
	fmt.Println(words)  
}
```

반환할 변수를 미리 지정하는 형식의 함수 작성도 가능하다.
```go
package main

import "fmt"

func main() {
	length, upper_word := nakedFunc("another word")  
	fmt.Println(length, upper_word)
}

func nakedFunc(word string) (lenght int, uppercase string) {  
	// 반환할 변수를 미리 정의해 두었기에  
	lenght = len(word)  
	uppercase = strings.ToUpper(word)  
	return  
	// return에 변수를 따로 지정하지 않아도 된다.  
}
```

**defer**
defer 키워드로 함수가 끝난 뒤에 할 작업을 미리 등록할 수가 있다.
```go
package main

import "fmt"

func main() {
	length, upper_word := nakedFunc("another word")  
	fmt.Println(length, upper_word)
}

func nakedFunc(word string) (lenght int, uppercase string) { 
	defer fmt.Println("done")
	lenght = len(word)  
	uppercase = strings.ToUpper(word)  
	return
}
```

위 처럼 함수 작성 시 defer를 사용하면 아래 처럼 값이 출력된다.
```bash
done
12 ANOTHER WORD
```

## Loop

go에서 반복문은 for 밖에 없다. 

```go
package main  
  
import "fmt"  
  
func main() {  
	loopWithRange()
}  
  
func loopWithRange() {  
	var arr = [3]int{1, 2, 3}  
	for index, element := range arr {  
		fmt.Println(index, element)  
	}  
}
```

```bash
0 1
1 2
2 3
```

보통 위 처럼 range와 같이 for를 사용하는 것 같다.
물론 range 없이 위와 동일하게 작동하는 for를 사용할 수도 있다.

```go
package main  
  
import "fmt"  
  
func main() {  
	loopWithoutRange()
} 

func loopWithoutRange() {  
	var arr = [3]int{1, 2, 3}  
	for i := 0; i < len(arr); i++ {  
		fmt.Println(i, arr[i])  
	}  
}
```

```bash
0 1
1 2
2 3
```

결과는 동일한데... 나는 range를 쓰는게 좋을 것 같다.
range는 참고로 for문 안에서만 사용 가능하다.

아래 처럼 ...type으로 받은 인자를 바로 for 문에 적용 가능하다.
```go
package main  
  
import "fmt"  
  
func main() {  
	result := loopWithParameter(1, 2, 3, 4, 5)
	fmt.Println(result)
} 

func loopWithParameter(numbers ...int) int {  
	sum := 0  
	for _, number := range numbers {
		// index가 필요 없다면 python과 동일하게 _(언더바)를 사용해주면 된다.
		sum += number  
	}  
	return sum  
}
```

```bash
15
```

## Conditional

go에서는 조건문의 조건식에서 변수를 정의할 수 있다.
아래는 일반적으로 if문을 사용하는 예시와 if문에서 변수를 정의하면서 사용하는 예시다.
```go
package main  
  
import "fmt"

func main() {  
	fmt.Println(commonIf(28))  
	fmt.Println(defineVariableIf(28))  
}  
  
func commonIf(age int) bool {  
	if age < 18 {  
		return false  
	}  
	return true  
}  
  
func defineVariableIf(age int) bool {  
	if koreanAge := age + 2; koreanAge < 18 {  
		return false  
	}  
	return true  
}
```

```bash
true
true
```

위 같은 문법을 variable expression이라 부른다고 한다.
변수를 따로 정의 하는 것 보다 좋은 점은 타인이 봤을 때 명확히 조건식에만 사용되는 변수라는 것을 알 수 있다는 점이다.

switch는 아래 처럼 사용하며 if문과 마찬가지로 조건식에서 변수 정의가 가능하다.
```go
package main  
  
import "fmt"  
  
func main() {  
	fmt.Println(useSwitch(39))  
}

func useSwitch(age int) bool {  
	switch age {  
		case 10:  
			return false  
		case 18:  
			return true  
	}  
	return false  
}

// 아래 형식으로도 작성 가능하다.
func useSwitch2(age int) bool {  
	switch {  
	case age < 18:  
		return false  
	case age == 18:  
		return true  
	case age > 50:  
		return false  
	}  
	return false  
}
```

## Pointer

다음 코드의 출력 값을 예상해보자.
```go
package main  
  
import "fmt"  
  
func main() {  
	a := 5
	b := a
	a = 12
	fmt.Println(a, b)  
}
```

12, 5 or 12, 12? 출력해서 확인해보면 10, 2가 출력된다.

이 말은 b := a 코드를 실행할 때 a 변수의 메모리 주소를 주는 것이 아니라 저장된 값을 복사에서 b에 넘겨주고 있기 때문에 a = 10 코드에서 b에는 아무런 영향을 받지 않는다는 말이다.

그런데 어떤 상황에서는 값을 복사하는 것이 아닌 메모리 주소를 필요로 할 수도 있다.

```go
package main  
  
import "fmt"  
  
func main() {  
	a := 5  
	b := &a  
	a = 12  
	fmt.Println(a, *b)
}
```
위 처럼 주소를 전달하고 싶을 땐 &를 이용하고 b 앞에 * 별을 붙힌 이유는 b를 출력 시 주소가 그대로 출력되기 때문이다. 메모리주소에 담긴 값을 출력하고 싶다면 * 을 앞에 붙혀 사용한다.

아래 코드를 보면 더 이해가 될 것이다.
```go
package main  
  
import "fmt"  
  
func main() {  
	a := 5  
	b := &a  
	*b = 20  
	fmt.Println(a, *b)
}
```
위 코드는 20, 20이 출력되며 b로도 a의 값을 변경 가능하다.
쉽게 말해서 &를 붙히면 변수의 주소를 * 를 붙히면 주소의 값을 바라볼 수 있다.
>b는 a를 살펴보는 pointer가 된다.

## Array

go의 array는 길이를 제한 하는 방법과 그렇지 않은 방법으로 나뉜다.
그리고 길이가 제한 되지 않은 array를 slice라고 부른다.

```go
package main  
  
import "fmt"  
  
func main() {  
	defineArray()  
	defineSlice()  
}  
  
func defineArray() {  
	arr := [4]int{1, 2, 3}  
	arr[3] = 4  
	// arr[4] = 5 -> 오류 발생  
	// 위 처럼 array 정의 시 길이가 4로 고정된다.  
	fmt.Println(arr)  
}  
  
func defineSlice() {  
	ex_slice := []int{1, 2}  
	// ex_slice[2] = 3 -> 오류 발생  
	// slice는 요소를 추가할 때 append 함수를 사용한다.  
	ex_slice = append(ex_slice, 3)  
	// append는 새로운 요소가 추가 된 slice를 반환하기에 값을 꼭 받아야 한다.  
	fmt.Println(ex_slice)  
}
```

코드를 보면 알 수 있듯이 배열의 요소들의 타입을 지정해야 한다.
```go
arr := [...]int{1, 2, 3}
```
그리고 위 같은 방식으로도 배열을 정의할 수 있으며 이 때 뒤에 입력한 요소의 갯수 만큼 자동으로 배열의 길이가 정해진다.

>slice에 요소 없이 비어있는 slice로도 정의가 가능하다.

## Map

python의 dict 같은 건데 좀 다르다.
map도 key와 value의 타입을 지정해주어야 하며 지정한 타입으로만 요소를 추가할 수 있다.

```go
package main  
  
import "fmt"  
  
func main() {  
	defineMap()  
}  
  
func defineMap() {  
	ex_map := map[string]int{"height": 173, "weight": 75}  
	ex_map["age"] = 28  
	// 키, 값 생성 
	// ex_map[29] = "map" -> 오류 발생
	fmt.Println(ex_map["height"])  
	// 키로 값 조회  
}  
```

array와 마찬가지로 range를 활용하여 반복문으로 사용 가능하다.
```go
func loopWithMap(iter map[string]int) {  
	for key, value := range iter {  
		// 필요 없는 값은 _(언더바)를 기재한다.  
		fmt.Println(key, value)  
	}  
}  
```

map에 특정 key가 존재하는지 확인할 때는 다음 처럼 사용한다.
```go
func checkKey(ex_map map[string]int) {  
	val, exists := ex_map["any"]  
	// go에서는 key로 map을 조회 시 2개의 값을 return 한다.  
	// 첫번째는 키에 상응하는 값, 두번째는 키가 존재하는지 안 하는지에 대한 bool 값.  
	if !exists {  
		println("Not in age")
	}  
	println(val)  
}
```

또한 map안에 찾는 키가 존재하지 않는다면 **reference 타입인 경우 nil**을 **value 타입인 경우 zero**를 리턴한다.

## Struct

go에서 map은 key와 value의 타입이 정의할 때 지정해둔 타입으로 고정된다.
다른 타입으로 데이터를 추가하려고 하면 오류가 발생한다.

반면에 struct는 좀 더 유연하게 사용이 가능하다.

```go
package main  
  
import "fmt"  

type restaurant struct {  
	name string  
	classification string  
	menuPrice map[string]int  
}
// struct 정의 방법, class 변수 만드는 느낌이다.
// 모든 자료형을 다 넣을 수 있다.

func main() {  
	menuPrice := map[string]int{"kimbab": 4000, "tunaKimbab": 6000}  
	kimbabHeaven := restaurant{"kimbabHeaven", "snackBar", menuPrice}  
	fmt.Println(kimbabHeaven)
	fmt.Println(kimbabHeaven.name)
	// . 을 통해 struct 내부 변수에 접근 가능하다.  
}  
  
```

다만 위  처럼 사용할 경우 struct 정의 후 해당 위치의 값이 뭘 의미하는지 알아보기 위해 struct를 
다시 들여다 보게 될 것이다. 때문에 보통 아래 처럼 작성한다.

```go
package main  
  
import "fmt"  

type restaurant struct {  
	name string  
	classification string  
	menuPrice map[string]int  
}

func main() {  
	menuPrice := map[string]int{"kimbab": 4000, "tunaKimbab": 6000}  
	kimbabHeaven := restaurant{  
		name: "kimbabHeaven",  
		classification: "snackBar",  
		menuPrice: menuPrice,  
	}
	fmt.Println(kimbabHeaven)
	fmt.Println(kimbabHeaven.name)
}  
```

python의 keyword 인자 처럼 사용하면 된다.
>다만 field: value 형태로 한번 적었다면 모든 변수를 다 같은 형식으로 작성해야한다.

여러모로 다른 언어들의 Class와 비슷한 느낌이지만 struct에는 생성자 함수가 없어서 따로 생성자 메서드를 만들고 직접 실행해주어야한다.

만약 외부 패키지에 있는 struct를 참조해야한다면 함수에서 그랬던 것 처럼 struct 명이 소문자로 시작하면 private, 대문자로 시작하면 public 이다. struct 뿐만 아니라 내부의 변수들도 마찬가지다.

```go
package public  
  
type PublicStruct struct {  
	AnyString string  
	AnyInt int  
}  
  
type privateStruct struct {  
	anyString string  
	anyInt int  
}
```

```go
package main

import (  
	"fmt"  
	"github.com/YunKyungho/learn-golang/structs/public"  
)  
  
func main() {  
  
	ps := public.PublicStruct{AnyString: "any", AnyInt: 93}  
	fmt.Println(ps)  
	// public.privateStruct -> 오류 발생  
}
```

그런데 문제는 public으로 작성 시 아래 처럼 변수의 값을 변경하기 매우 쉬워진다.
```go
func main() {  
  
	ps := public.PublicStruct{AnyString: "any", AnyInt: 93}  
	fmt.Println(ps)  
	// public.privateStruct -> 오류 발생  
	ps.AnyString = "diff"
}
```

### constructor

외부 패키지로 struct를 export 하지만 내부 변수는 외부의 접근을 막고 싶다면 생성자를 사용하여 struct를 생성해야 한다. Go에서 생성자를 만드는 방식은 다음과 같다.
```go
package public  
    
type privateStruct struct {  
	anyString string  
	anyInt int  
}

func PublicFunc(anyString string) *privateStruct {  
	ps := privateStruct{anyString: anyString, anyInt: 0}  
	return &ps  
}
```

main에서는 다음과 같이 사용한다.
```go
func main() {  
	useConstructorPs := public.PublicFunc("any")  
	fmt.Println(*useConstructorPs)  
	// useConstructorPs.anyString = "another" -> 오류 발생  
	// useConstructorPs.anyInt = 1818 -> 오류 발생  
}
```

>구조체의 복사본이 아닌 포인터로 반환 하는 이유는 더 효율적이기 때문이다.
>메모리 복사는 오버헤드가 크며 성능을 저하할 수 있다.

다만 이렇게 사용할 시 외부에서는 전혀 내부 변수의 값을 변경할 수 없다.
이럴 때 method를 만들어서 사용한다.

### method

```go
// project_root/method/main.go

package main  
  
import "github.com/YunKyungho/learn-golang/method/myStruct"  
  
func main() {  
	account := myStruct.NewAccount("ygh")  
	account.Deposit(10)  
}
```

```go
// project_root/method/myStruct/test.go

package myStruct  
  
type Account struct {  
	owner string  
	balance int  
}  

// go에서의 constructor
func NewAccount(owner string) *Account {  
	account := Account{owner: owner, balance: 0}  
	return &account  
}  

// go에서의 method
func (a Account) Deposit(amount int) {  
	// 여기서 a는 receiver라고 불리며 a의 type은 Account이다.
	// struct의 첫 글자를 소문자로 사용하는 것이 관행이다.
	a.balance += amount  
}
```

>위에서 볼 수 있듯이 go의 메소드는 다른 PL 처럼 class(struct) 내부에 정의되지 않고
>위 같은 방식으로 표현한다.

만약 main에서 account의 balance를 출력하고 싶다면 getter가 필요할 것이다.
```go
// project_root/method/myStruct/test.go

func (a Account) Balance() int {  
	return a.balance  
}
```

main에서는 아래 처럼 사용한다.
```go
package main  
  
import (  
	"fmt"  
	"github.com/YunKyungho/learn-golang/method/myStruct"  
)  
  
func main() {  
	account := myStruct.NewAccount("ygh")  
	account.Deposit(10)  
	fmt.Println(account.Balance())  
}
```

실행해보면 알겠지만 문제가 있다. 10이 아닌 Account struct의 balance 기본 값인 0이 출력된다.

문제는 method의 receiver에 있다. 아래는 위 코드를 수정한 것이다.
```go
// project_root/method/myStruct/test.go

package myStruct  
  
type Account struct {  
	owner string  
	balance int  
}  

// go에서의 constructor
func NewAccount(owner string) *Account {  
	account := Account{owner: owner, balance: 0}  
	return &account  
}  

// go에서의 method
func (a *Account) Deposit(amount int) {  
	a.balance += amount  
}

// go에서의 getter
func (a *Account) Balance() int {  
	return a.balance  
}
```

method의 receiver에 사용될 struct 앞에는 꼭 * 을 붙혀주어야한다.

Go는 함수를 실행할 때나 반환할 때 변수에 * 을 붙히지 않으면 항상 복사본을 만들어 receive 하거나 return 한다. 위에서 값이 0이 출력됬던 것도 Deposit() method 실행 시 생성했던 account의 복사본을 받아와서 값을 변경 했기에 원본 account에는 어떠한 영향도 끼치지 않았던 것이다.

### magic method?
python과 마찬가지로 어떻게 사용되냐에 따라 자동으로 호출되는 magic method 같은 개념이 go에서도 존재한다. (반복문에 이터레이터로 사용될 객체를 지정하면 자동으로 해당 객체의 next method를 호출하는 등의 기능)

Account struct에 다음 method를 추가한 뒤 실행시켜 보자.
```go
func (a *Account) Owner() string {  
	return a.owner  
}  
  
func (a *Account) String() string {  
	return fmt.Sprint(a.Owner(), "'s account.\nHas: ", a.Balance())  
}
```

```go
// main.go

package main  
  
import (  
	"fmt"  
	"github.com/YunKyungho/learn-golang/except/accounts"  
	"log"  
)  
  
func main() {  
	account := accounts.NewAccount("ygh")  
	account.Deposit(10)  
	fmt.Println(account)  
}

```

String 함수 작성 전 기존 fmt.Println(account) 실행 시 &{owner, balance} 형식으로 출력됬던 반면
아래 처럼 값이 출력됬을 것이다.
```bash
ygh's account.
Has: 10 
```

## Except

먼저 Go에는 try - catch나 try - except 같은 문법이 없다.
직접 if 문을 통해 확인하고 error를 return 하는 식으로 function을 만들어야 한다.
또한 이를 호출한 곳에서 직접 예외처리를 해주어야 한다.

위의 Account struct의 계좌에서 돈을 출금하는 Withdraw라는 method를 만들어보자.
```go
import "errors"

func (a *Account) Withdraw(amount int) error {  
	if a.balance < amount {  
		return errors.New("insufficient balance")  
	}  
	a.balance -= amount  
	return nil  
}
```
위 코드가 일반적인 에러 반환 방법이다. 
>자주 쓰는 error 같은 경우 errors.New()를 변수에 저장해두고 변수를 return 하는 방식으로도 사용된다.

error를 반환한다고 해서 go에서 알아서 에러처리를 해주지 않는다.
main에서 이를 사용할 때 다음과 같은 분기처리가 필요하다.
```go
package main  
  
import (  
	"fmt"  
	"github.com/YunKyungho/learn-golang/except/accounts"  
	"log"  
)  
  
func main() {  
	account := accounts.NewAccount("ygh")  
	account.Deposit(10)  
	fmt.Println(account.Balance())  
	
	err := account.Withdraw(20)  
	if err != nil {  
		log.Fatalln(err)  
	}  
}
```
함수 처리 결과를 err 변수에 저장하고 nil(error가 아닌 경우)이 아닐 때 log.Fatalln 함수를 실행한다.
(log.Fatalln는 오류 문구를 출력하고 프로그램을 종료한다.)

>error 처리를 전부 직접 해야 되서 매우 귀찮긴 하지만 error를 체크하도록 강제 시킨다는 점에서 괜찮은 것 같다.

## Type

struct에 method를 만들 수 있었던 것은 struct의 성질 때문이 아니라 type의 성질 때문이었다.
이 말은 struct 뿐만 아니라 다른 타입의 자료형에도 method를 만들어줄 수 있다는 것이다.

map을 통해 설명 해보자.
```go
// project_root/dict/myDict/myDict.go

package myDict  
  
import "errors"  
  
type Dictionary map[string]string  
// type은 int도 되고 string도 되고 다 된다.
  
var errNotFound = errors.New("Not Found")  
  
func (d Dictionary) Search(word string) (string, error) {  
	value, exists := d[word]  
	// 무슨 의미인지 모르겠다면 map 단원을 보고 오자.
	if exists {  
		return value, nil  
	}  
	return "", errNotFound  
}
```

struct 단원에서 method를 설명할 때와 동일하게 receiver를 통해 Dictionary의 method를 만들었다.
main에서 이전에 만든 struct의 method와 동일하게 사용 가능하다.

```go
// project_root/dict/main.go

package main  
  
import (  
	"fmt"  
	"github.com/YunKyungho/learn-golang/dict/myDict"  
)  
  
func main() {  
	dictionary := myDict.Dictionary{"first": "First word"}
	// 기본적인 map 생성 방식.  
	definition, err := dictionary.Search("second")  
	if err != nil {  
		fmt.Println(err)  
	} else {  
		fmt.Println(definition)  
	}  
}
```

예시를 위한 설명이지 실제로 map을 이렇게 쓰는지는 모르겠으나, 위 같은 방식으로 python에 있는 dict의 get method나 setdefault method를 만드는 것은 유용할 수도 있겠다. 

