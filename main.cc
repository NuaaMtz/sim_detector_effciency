#include "chrono"
#include "globals.hh"
#include "iostream"
// run管理器，多线程与单线程模式
#ifdef G4MULTITHREADED
#include "G4MTRunManager.hh"
#else
#include "G4RunManager.hh"
#endif

#include "DEConstruction.hh"
#include "FTFP_BERT.hh"
#include "G4DecayPhysics.hh"
#include "G4RadioactiveDecayPhysics.hh"
#include "InitializationAction.hh"

#include "ConstructionManager.hh"
// 可视化
#include "G4UIExecutive.hh"
#include "G4UImanager.hh"
#include "G4VisExecutive.hh"

int main(int argc, char **argv) {
  // 开始时间
  auto start = std::chrono::high_resolution_clock::now(); // 记录开始时间
  printf("开始模拟!");

  // 根据指定的值来判断是否打开运行管理器或 mtrun 管理器
#ifdef G4MULTITHREADED
  G4MTRunManager *runManager = new G4MTRunManager;
#else
  G4RunManager *runManager = new G4RunManager;
#endif
  // 手动限制线程
  int thread = 32;
  runManager->SetNumberOfThreads(thread);

  DEConstruction *detector = new DEConstruction();

  G4VModularPhysicsList *physicallist = new FTFP_BERT();
  physicallist->RegisterPhysics(new G4DecayPhysics());
  physicallist->RegisterPhysics(new G4RadioactiveDecayPhysics());

  runManager->SetUserInitialization(detector);
  new ConstructionManager(detector);
  runManager->SetUserInitialization(physicallist);
  runManager->SetUserInitialization(new InitializationAction(detector));

  //* 可视化

  G4VisManager *visManager = new G4VisExecutive;
  visManager->Initialize();

  G4int verboseLevel = 0;
  G4RunManager::GetRunManager()->SetVerboseLevel(verboseLevel);

  G4UImanager *UImanager = G4UImanager::GetUIpointer();

  // Process macro or start UI session
  G4UIExecutive *ui = 0;
  if (argc == 1) {
    ui = new G4UIExecutive(argc, argv);
  }

  if (!ui) {
    // batch mode
    G4String command = "/control/execute ";
    G4String fileName = argv[1];
    UImanager->ApplyCommand(command + fileName);
  } else {
    // interactive mode
    UImanager->ApplyCommand("/control/execute ../vis.mac");
    ui->SessionStart();
    delete ui;
  }

  // free the memory
  delete visManager;
  delete runManager;

  // 输出运行记录
  auto end = std::chrono::high_resolution_clock::now(); // 记录结束时间
  std::chrono::duration<double> elapsed = end - start;
  std::cout << "程序运行时间: " << elapsed.count() << " 秒" << std::endl;

  return 0;
}