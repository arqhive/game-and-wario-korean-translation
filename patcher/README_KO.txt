게임앤와리오 (Wii U) 한글 패치 {VER}
제작: arqhive

「ゲーム&ワリオ」(Wii U, 일본판) 비공식 한국어 팬 패치입니다.
게임 속 대사·메뉴·설명과 그림 글씨를 한글로 바꿉니다.


[준비물]

- 일본판 「ゲーム&ワリオ」(타이틀 ID 0005000010112D00)의 복호화된 게임 파일.
  content\Common\Msg\JP_Japanese 폴더 안에 msbt.warc.fzip 이 있어야 합니다.
  북미판(Game & Wario)에는 적용할 수 없습니다.
- 윈도우 PC.
- Wii U 실기: Aroma와 SDCafiine 플러그인, SD 카드.
- 에뮬레이터: Cemu.


[한글판 만들기]

1. ASAJ_KPatch_{VER}.zip 을 폴더째 압축을 풉니다. ASAJ_KPatch_{VER} 폴더가 생깁니다.
2. 게임 폴더(content 폴더가 들어 있는 폴더)를 "패치하기.bat"에 끌어다 놓습니다.
   그냥 실행하면 경로를 묻습니다.
3. 원본 확인 → 한글판 만들기 → 결과 확인이 차례로 진행됩니다.
   결과는 ASAJ_KPatch_{VER}\출력 폴더에 생깁니다. 원본 파일은 바뀌지 않습니다.

- 이미 패치한 파일이나 다른 판을 넣으면 원본 확인 단계에서 멈춥니다.


[Wii U 실기 (SDCafiine)]

1. 출력\sdcafiine 폴더 안의 내용을 SD 카드의 wiiu\sdcafiine\ 에 복사합니다.
   다음과 같이 파일이 놓이면 됩니다.

     sd:/wiiu/sdcafiine/0005000010112D00/GameWarioKR/content/Common/...

2. SDCafiine 플러그인을 켠 상태로 게임을 실행합니다.

- 타이틀의 「시작」처럼 일부 글자는 Wii U 본체 글꼴로 나옵니다.
  본체 글꼴에 한글이 들어 있어야 보이고, 그렇지 않으면 ?? 로 보일 수 있습니다.


[Cemu]

1. 출력\cemu\GameWarioKR 폴더를 Cemu 의 graphicPacks 폴더에 복사합니다.
2. Cemu 의 그래픽팩 설정에서 Game & Wario → Mods → Korean Patch 를 켭니다.
3. 게임을 실행합니다.


[면책]

비공식 팬 번역이며 Nintendo와 관련이 없습니다.
「ゲーム&ワリオ」 관련 상표·저작권은 각 권리자에게 있습니다.
패치를 적용한 게임 파일의 배포를 금지합니다.
한글 글자는 메이플스토리 Bold, 충주김생체, 둘기마요 글꼴로 만들었습니다.
패처에 쓴 프로그램의 라이선스는 licenses 폴더에 있습니다.
